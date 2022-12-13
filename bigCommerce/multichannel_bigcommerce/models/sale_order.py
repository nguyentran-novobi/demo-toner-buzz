# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
import operator

from odoo import api, models, _, fields
from odoo.exceptions import ValidationError
from odoo.tools import float_round

from odoo.addons.channel_base_sdk.utils.common.exceptions import EmptyDataError

from ..utils.bigcommerce_order_helper import BigCommerceOrderHelper, BigCommerceOrderImporter,\
    BigCommerceOrderImportBuilder
from ..utils.bigcommerce_shipment_helper import BigCommerceShipmentImporter, BigCommerceShipmentImportBuilder

from odoo.addons.multichannel_order.models.sale_order import ShipmentImportError
from ..utils.order_processing_helper import BigCommerceOrderProcessingBuilder

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def bigcommerce_get_order_shipments(self, shipment_id=None):
        """
        Get shipments on Order.
        The result from this function will be called after order and order lines already created.

        An order on BigCommerce can have multiple shipment. And each shipment can have different shipping addresses
        :return: Create delivery orders for sale order
        """
        self.ensure_one()
        datas = []
        error_message = None
        StockPicking = self.env['stock.picking']
        try:
            for shipment_data in self.bigcommerce_import_shipments(shipment_id):
                datas.append(shipment_data)
            if datas and self.state == 'draft':
                self.action_confirm()
            StockPicking.process_shipment_data_from_channel(self, datas, self.channel_id)
        except Exception as e:
            error_message = str(e)
        return datas, error_message

    def bigcommerce_cancel_on_channel(self):
        self.ensure_one()
        helper = BigCommerceOrderHelper(self.channel_id)
        response = helper.cancel(self.id_on_channel)
        if not response.ok():
            title = 'Cannot update order status on Bigcommerce'
            exceptions = [{'title': 'Cannot update status on Channel', 'reason': response.get_error_message()}]
            self._log_exceptions_on_order(title, exceptions)
            return False
        return True
    
    @api.model
    def bigcommerce_get_data(self, channel_id, ids=None, from_date=None, to_date=None, update=None, all_records=False):
        return self.bigcommerce_import_orders(channel_id, ids or [], from_date, to_date, update, all_records)
    
    @api.model
    def bigcommerce_import_orders(
            self,
            channel_id,
            ids=None,
            from_date=None,
            to_date=None,
            update=None,
            all_records=False,
    ):
        
        def prepare_importer(chn, is_manual):
            res = BigCommerceOrderImporter()
            res.channel = chn
            res.ids = ids or []
            if is_manual:
                res.created_from_date = from_date
                res.created_to_date = to_date
            else:
                res.modified_from_date = from_date
                res.modified_to_date = to_date
            res.all_records = all_records
            return res

        def prepare_builder(order_data_list):
            res = BigCommerceOrderImportBuilder()
            res.orders = order_data_list
            return res

        datas, uuids = [], []
        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)
        importer = prepare_importer(channel, self.env.context.get('manual_import'))

        for pulled in importer.do_import():
            if pulled.ok():
                order_data = list(map(operator.attrgetter('data'), pulled))
                datas.extend(order_data)
                builder = prepare_builder(order_data)
                for order_vals in builder.prepare():
                    record = self.sudo().search([
                        ('channel_id', '=', channel_id),
                        ('id_on_channel', '=', str(order_vals['id'])),
                    ], limit=1)

                    existed_record = bool(record)  # If sale order has already existed

                    uuids.extend(self.create_jobs_for_synching(
                        vals_list=[order_vals],
                        channel_id=channel_id,
                        update=existed_record,
                    ))
                    self._cr.commit()
            elif pulled.last_response and not pulled.last_response.ok():
                _logger.error('Error while importing orders: %s', pulled.get_error_message())
                channel.sudo().disconnect()
        return datas, uuids

    def bigcommerce_import_shipments(self, shipment_id=None):
        self.ensure_one()
     
        def prepare_importer():
            res = BigCommerceShipmentImporter()
            res.channel = self.channel_id
            res.order_id = self.id_on_channel
            res.shipment_id = shipment_id
            return res
        
        def prepare_builder(shipment_data):
            res = BigCommerceShipmentImportBuilder()
            if isinstance(shipment_data, dict):
                shipment_data = [shipment_data]
            res.shipments = shipment_data
            return res
        
        def fetch_shipment(gen):
            yield from gen
                
        importer = prepare_importer()
        for pulled in importer.do_import():
            if pulled.ok():
                if pulled.data:
                    builder = prepare_builder(pulled.data)
                    yield from fetch_shipment(builder.prepare())
            else:
                raise ShipmentImportError(pulled.get_error_message())

    @api.model
    def _process_order_data(self, order_data, order_configuration, channel, products, search_on_mapping):
        # In case the channel is not BigCommerce or it is BigCommerce but the manage_taxes_on_order_lines setting is not active
        if not channel.is_bigcommerce_manage_taxes_on_order_lines():
            return super(SaleOrder, self)._process_order_data(order_data, order_configuration, channel, products, search_on_mapping)

        # Opposite case
        def bigcommerce_prepare_builder(order_data, channel_id):
            res = BigCommerceOrderProcessingBuilder()
            res.order_data = order_data
            res.channel_id = channel_id
            res.default_product_ids = order_configuration['default_product_ids']
            return res

        builder = bigcommerce_prepare_builder(order_data, channel.id)
        gen = builder.prepare_order_data()
        content = next(gen)
        order_vals = gen.send(self._prepare_imported_order_lines(channel, content, products, search_on_mapping))
        order_vals.update(self._extend_ecommerce_order_vals(channel, order_data))

        self._update_other_fees_taxes(order_vals, channel)

        return order_vals

    @api.model
    def _prepare_imported_order_lines(self, channel, lines, products, search_on_mapping):
        # In case the channel is not BigCommerce or it is BigCommerce but the manage_taxes_on_order_lines setting is not active
        if not channel.is_bigcommerce_manage_taxes_on_order_lines():
            return super(SaleOrder, self)._prepare_imported_order_lines(channel, lines, products, search_on_mapping)

        # Opposite case
        ln_vals = []
        company_id = channel.company_id.id
        get_bigcommerce_tax_by_amount = self.env['account.tax'].get_bigcommerce_tax_by_amount
        for line in lines:
            if not search_on_mapping:
                product = products.filtered(lambda p: p.default_code == line['sku'])
                if not product:
                    raise ValidationError(_('Missing SKU %s', line['sku']))
                line['product_id'] = product[0].id
            else:
                tax_id = get_bigcommerce_tax_by_amount(line.get('tax_amount', 0), company_id).id
                if 'tax_amount' in line:
                    del line['tax_amount']
                if line['product_id'] in ['0', 'None']:
                    line_dup = dict(line)
                    line['product_id'] = {
                        '_m': 'sale.order',
                        '_i': (),
                        '_f': '_prepare_imported_order_lines_generate_custom_product_id',
                        '_a': (line_dup,),
                        '_k': {},
                    }
                    if tax_id:
                        line['tax_id'] = [fields.Command.clear(), fields.Command.link(tax_id)]
                else:
                    listing = self._prepare_imported_order_lines_get_listing_mapping(line, products, channel)
                    if listing:
                        mapping_quantity = listing.mapping_quantity
                        line.update({
                            'product_id': listing.product_product_id.id,
                            'quantity': line['quantity'] * mapping_quantity,
                            'price': float_round(float(line['price']) / mapping_quantity, precision_digits=2),
                            'tax_id': [fields.Command.clear()]
                        })
                        if tax_id:
                            line['tax_id'].append(fields.Command.link(tax_id))

            ln_vals.append((0, 0, self._prepare_order_line(channel, line)))
        return ln_vals

    @api.model
    def _prepare_order_line(self, channel, line_data):
        res = super()._prepare_order_line(channel, line_data)
        if channel.is_bigcommerce_manage_taxes_on_order_lines():
            res['tax_id'] = line_data.get('tax_id') or [fields.Command.clear()]
        return res

    @api.model
    def _update_other_fees_taxes(self, order_vals, channel):
        if 'order_line' in order_vals:
            company_id = channel.company_id.id
            get_bigcommerce_tax_by_amount = self.env['account.tax'].get_bigcommerce_tax_by_amount

            for line in order_vals['order_line']:
                _, _, line_data = line

                if type(line_data) == dict and line_data.get('display_type') not in ('line_section', 'line_note'):
                    for key in ['is_delivery', 'is_handling', 'is_wrapping', 'is_other_fees']:
                        if line_data.get(key, False):
                            tax_id = get_bigcommerce_tax_by_amount(line_data.get('tax_amount', 0), company_id).id
                            if tax_id:
                                line[2]['tax_id'].append(fields.Command.link(tax_id))
                            del line[2]['tax_amount']

        return order_vals