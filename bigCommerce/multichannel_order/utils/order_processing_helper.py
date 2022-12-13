from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter
from odoo.tools.float_utils import float_compare
from typing import Any

class SingularOrderDataInTrans(common_formatter.DataTrans):

    def __call__(self, order_data, channel_id, default_product_ids):
        header_content = self._process_header_content(channel_id, order_data)
        notes = self._process_notes(order_data)
        warehouse = self._prcess_warehouse(order_data)
        discount_lines = self._process_discount_lines(order_data, default_product_ids)
        fee_lines = self._process_fee_lines(order_data, default_product_ids)
        tax_lines = self._process_tax_lines(order_data, default_product_ids)
        lines = [(5, 0, 0)] + discount_lines + fee_lines + tax_lines
        result = {
            **header_content,
            **notes,
            **warehouse,
            **{'order_line': lines}
        }
        return result

    @classmethod
    def _process_header_content(cls, channel_id, order_data):
        return {
            'name': order_data['name'],
            'partner_id': order_data['partner_id'],
            'partner_invoice_id': order_data['partner_invoice_id'],
            'partner_shipping_id': order_data['partner_shipping_id'],
            'updated_shipping_address_id': order_data['updated_shipping_address_id'],
            'customer_channel_id': order_data['customer_channel_id'],
            'channel_id': channel_id,
            'id_on_channel': str(order_data['id']),
            'channel_date_created': order_data['channel_date_created'].replace(tzinfo=None),
            'date_order': order_data['channel_date_created'].replace(tzinfo=None),
            'channel_order_ref': order_data['channel_order_ref'],
            'requested_shipping_method': order_data.get('requested_shipping_method'),
            'order_status_channel_id': order_data['order_status_channel_id'],
            'payment_status_channel_id': order_data['payment_status_channel_id'],
            'payment_gateway_code': order_data.get('payment_gateway_code', ''),
            'picking_policy': order_data['picking_policy'],
            'team_id': order_data['team_id'],
            'company_id': order_data['company_id'],
            'pricelist_id': order_data['pricelist_id'],
        }

    @classmethod
    def _process_notes(cls, order_data):
        return {
            'staff_notes': order_data.get('staff_notes'),
            'customer_message': order_data.get('customer_message'),
        }

    @classmethod
    def _prcess_warehouse(cls, order_data):
        return {
            'warehouse_id': order_data['warehouse_id']
        } if order_data['warehouse_id'] else {}

    @classmethod
    def _process_discount_lines(cls, order_data, default_product_ids):
        lines = []
        has_discount = float_compare(order_data.get('discount_amount', 0), 0, precision_digits=2) > 0

        if has_discount or order_data.get('coupons', []):
            lines.append((0, 0, {'display_type': 'line_section',
                                 'sequence': 2,
                                 'name': 'Discounts'}))

        if has_discount:
            discount_vals = {
                'product_id': default_product_ids['discount'],
                'name': 'Discounts',
                'price_unit': float(-(order_data['discount_amount'])),
                'tax_id': [(5, 0, 0)],
                'is_discount': True,
                'sequence': 3
            }
            lines.append((0, 0, discount_vals))
            if order_data.get('discount_notes', []):
                notes = '\n'.join(order_data['discount_notes'])
                lines.append((0, 0, {'display_type': 'line_note', 'name': notes, 'sequence': 3}))
        #
        # Check if there is any coupons for order
        #

        if order_data.get('coupons', {}):
            coupons = order_data['coupons']
            for code, amount in coupons.items():
                # Create discount line
                coupons_vals = {
                    'product_id': default_product_ids['discount'],
                    'name': code,
                    'price_unit': float(-(amount)),
                    'tax_id': [(5, 0, 0)],
                    'is_coupon': True,
                    'sequence': 3
                }
                lines.append((0, 0, coupons_vals))
        return lines

    @classmethod
    def _process_fee_lines(cls, order_data, default_product_ids):
        lines = []
        for key in ['shipping', 'handling', 'wrapping', 'other_fees']:
            if float_compare(float(order_data.get('%s_cost' % key, 0)), 0, precision_digits=2) > 0:
                vals = {
                    'product_id': default_product_ids[key],
                    'product_uom_qty': 1,
                    'name': ('%s Cost' % key).replace('_', ' ').title(),
                    'price_unit': order_data.get('%s_cost' % key, 0),
                    'tax_id': [(5, 0, 0)],
                    'is_delivery': True if key == 'shipping' else False,
                    'is_handling': True if key == 'handling' else False,
                    'is_wrapping': True if key == 'wrapping' else False,
                    'is_other_fees': True if key == 'other_fees' else False,
                    'sequence': 5
                }
                lines.append((0, 0, vals))
        if lines:
            lines.append((0, 0, {'display_type': 'line_section', 'name': 'Other Fees', 'sequence': 4}))
        return lines

    @classmethod
    def _process_tax_lines(cls, order_data, default_product_ids):
        lines = []
        if order_data.get('taxes'):
            tax_vals = []
            for tax in order_data['taxes']:
                if float_compare(float(tax['amount']), 0, precision_digits=2) > 0:
                    tax_vals.append({
                        'product_id': default_product_ids['tax'],
                        'product_uom_qty': 1,
                        'name': tax['name'],
                        'price_unit': tax['amount'],
                        'is_tax': True,
                        'sequence': 7,
                        'tax_id': [(5, 0, 0)],
                    })
            if tax_vals:
                lines.append((0, 0, {'display_type': 'line_section', 'name': 'Taxes', 'sequence': 6}))
                lines.extend((0, 0, vals) for vals in tax_vals)
            if order_data.get('tax_notes', []):
                notes = '\n'.join(order_data['tax_notes'])
                lines.append((0, 0, {'display_type': 'line_note', 'name': notes, 'sequence': 7}))
        return lines

class OrderProcessingBuilder:
    order_data: Any
    channel_id: int
    default_product_ids: dict
    transform_data = SingularOrderDataInTrans()

    def prepare_order_data(self):
        transformed_data = self.transform_data(self.order_data, self.channel_id, self.default_product_ids)
        content = yield self.order_data['lines']
        transformed_data['order_line'].extend(content)
        yield transformed_data
