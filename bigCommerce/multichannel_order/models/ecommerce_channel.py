# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
import json

from datetime import datetime, timedelta
from babel.dates import format_date

from odoo import api, fields, models, _
from odoo.tools.misc import get_lang

_logger = logging.getLogger(__name__)


class EcommerceChannel(models.Model):
    _inherit = "ecommerce.channel"

    allow_update_order = fields.Boolean('Allow to update orders after the first sync', default=True)
    kanban_dashboard_graph = fields.Text(compute='_kanban_dashboard_graph')

    order_prefix = fields.Char(string='Order Prefix')
    sales_team_id = fields.Many2one('crm.team', string='Sales Team')
    min_order_date_to_import = fields.Date('Order Date to Import')
    default_guest_customer = fields.Char(string='Guest Customer Name', required=True, default='Guest')
    default_tax_product_id = fields.Many2one('product.product', string='Tax')
    default_discount_product_id = fields.Many2one('product.product', string='Discount')
    default_fee_product_id = fields.Many2one('product.product', string='Fee')
    default_shipping_cost_product_id = fields.Many2one('product.product', string='Shipping Cost')
    default_handling_cost_product_id = fields.Many2one('product.product', string='Handling Cost')
    default_wrapping_cost_product_id = fields.Many2one('product.product', string='Wrapping Cost')

    default_shipping_policy = fields.Selection([
        ('direct', 'As soon as possible'),
        ('one', 'When all products are ready')],
        default=lambda self: self.env['ir.default'].get_model_defaults('sale.order').get('picking_policy') or 'direct',
        string='Shipping Policy',
        help="If you deliver all products at once, the delivery order will be scheduled based on the greatest "
        "product lead time. Otherwise, it will be based on the shortest.")

    order_process_rule_ids = fields.One2many('order.process.rule', 'channel_id', string='Actions')

    default_payment_journal_id = fields.Many2one('account.journal', string='Default Payment Journal',
                                                 domain="[('type', 'in', ['bank', 'cash'])]")

    default_payment_method_id = fields.Many2one('account.payment.method',
                                                string='Default Payment Method',
                                                readonly=False,
                                                store=True,
                                                compute='_compute_payment_method_id',
                                                domain="[('id', 'in', available_payment_method_ids)]")

    default_deposit_account_id = fields.Many2one(
        'account.account',
        string='Default Deposit Account',
        domain=lambda self: [
            ('user_type_id', 'in', [self.env.ref('account.data_account_type_current_liabilities').id]),
            ('deprecated', '=', False),
            ('reconcile', '=', True),
        ])

    payment_method_mapping_ids = fields.One2many('payment.method.mapping', 'channel_id', string='Payment Method Mapping')

    available_payment_method_ids = fields.Many2many(
        'account.payment.method', compute='_compute_payment_method_fields')

    @api.depends('default_payment_journal_id')
    def _compute_payment_method_fields(self):
        for record in self:
            available_payment_methods = record.default_payment_journal_id.mapped('inbound_payment_method_line_ids.payment_method_id')
            record.available_payment_method_ids = available_payment_methods

    @api.depends('default_payment_journal_id')
    def _compute_payment_method_id(self):
        for record in self:
            available_payment_method_ids = record.default_payment_journal_id.mapped('inbound_payment_method_line_ids.payment_method_id')
            if available_payment_method_ids:
                record.default_payment_method_id = available_payment_method_ids[0]._origin
            else:
                record.default_payment_method_id = False
    
    @api.onchange('default_payment_journal_id')
    def onchange_payment_journal(self):
        if self.default_payment_journal_id:
            inbound_payment_methods = self.default_payment_journal_id.mapped('inbound_payment_method_line_ids.payment_method_id')
            return {
                'domain': {'default_payment_method_id': [('id', 'in', inbound_payment_methods.ids)]},
                'value': {'default_payment_method_id': inbound_payment_methods[:1].id},
            }
        else:
            self.default_payment_method_id = False

    def _get_imported_fulfillment_statuses(self):
        self.ensure_one()
        return self.order_process_rule_ids.mapped('order_status_channel_ids')

    def _get_imported_payment_statuses(self):
        self.ensure_one()
        return self.order_process_rule_ids.mapped('payment_status_channel_ids')

    def _create_default_products(self):
        self.ensure_one()
        vals = {}
        def_prod_fields = [
            'default_tax_product_id', 'default_discount_product_id',
            'default_fee_product_id', 'default_shipping_cost_product_id',
            'default_handling_cost_product_id', 'default_wrapping_cost_product_id',
        ]
        products = ['Tax', 'Discount', 'Fee', 'Shipping Cost', 'Handling Cost', 'Wrapping Cost']
        for field, product in zip(def_prod_fields, products):
            product_vals = {
                'name': f"[{self.name}] {product}",
                'type': 'service',
                'sale_ok': False,
                'purchase_ok': False,
                'active': False,
                'invoice_policy': 'order'
            }
            template = self.env['product.template'].create(product_vals)
            vals[field] = template.with_context(active_test=False).product_variant_ids[0].id
        return vals

    def _get_order_configuration(self):
        return {
            'order_prefix': self.order_prefix,
            'sales_team_id': self.sales_team_id.id,
            'shipping_policy': self.default_shipping_policy,
            'default_product_ids': {
                'tax': self.default_tax_product_id.id,
                'discount': self.default_discount_product_id.id,
                'shipping': self.default_shipping_cost_product_id.id,
                'wrapping': self.default_wrapping_cost_product_id.id,
                'handling': self.default_handling_cost_product_id.id,
                'other_fees': self.default_fee_product_id.id
            },
            'imported_fulfillment_status_ids': self._get_imported_fulfillment_statuses().ids,
            'imported_payment_status_ids': self._get_imported_payment_statuses().ids,
            'warehouse_id': self.default_warehouse_id.id,
            'company_id': self.company_id.id
        }

    def _set_default_order_configuration(self):
        self.ensure_one()
        # Create Sales Team
        company_id = self.company_id.id
        sales_team = self.env['crm.team'].sudo().create({'name': self.name, 'company_id': company_id})
        # Default options
        default_warehouse = self.env['stock.warehouse'].sudo().search([('company_id', '=', company_id)], limit=1)

        default_products = self._create_default_products()
        self.update({
            **default_products,
            **{
                'sales_team_id': sales_team.id,
                'default_warehouse_id': default_warehouse.id
            }
        })

    def _kanban_dashboard_graph(self):
        for record in self:
            record.kanban_dashboard_graph = json.dumps(record.get_graph_datas())

    def get_graph_datas(self):
        last_30_days = datetime.now().replace(hour=0, minute=0, second=0) - timedelta(days=30)

        def build_graph_data(start_date, end_date, amount):
            # display date in locale format
            name = format_date(start_date, 'd LLLL Y', locale=locale)
            short_name = format_date(start_date, 'd MMM', locale=locale)
            short_name += ' - ' + format_date(end_date, 'd MMM', locale=locale)
            return {'x': short_name,
                    'y': amount,
                    'name': name}

        query = """
            SELECT DATE(o.date_order) AS order_date,
                  COALESCE(SUM(o.amount_total), 0) AS total
            FROM sale_order AS o
            WHERE o.date_order >= %s
              AND o.channel_id = %s
              AND o.state IN ('sale', 'done')
            GROUP BY order_date
        """
        locale = get_lang(self.env).code
        self.env.cr.execute(query, (last_30_days, self.id))
        query_result = self.env.cr.dictfetchall()
        data = []

        week_start = int(self.env['res.lang']._lang_get(self.env.user.lang).week_start) - 1
        week_end = week_start - 1 if week_start != 0 else 6

        # Set default
        today = datetime.today().replace(hour=23, minute=59, second=59)
        index = last_30_days
        while index < today:
            start_of_week = index.replace(hour=0, minute=0, second=0)
            shift = (7 + week_end - index.weekday()) % 7
            end_of_week = (index + timedelta(days=shift)).replace(hour=23, minute=59, second=59)
            if end_of_week > today:
                end_of_week = today
            rows = list(filter(lambda r: start_of_week.date() <= r['order_date'] <= end_of_week.date(), query_result))
            data.append(build_graph_data(start_of_week.date(), end_of_week.date(), sum([r['total'] for r in rows]) or 0))
            index = end_of_week + timedelta(days=1)

        return [{
            'values': data,
            'title': '',
            'key': _('Total sales'),
            'area': True, 'color': '#875A7B',
            'currency': {
                'symbol': self.env.company.currency_id.symbol,
                'position': self.env.company.currency_id.position,
                'id': self.env.company.currency_id.id
            }
        }]

    def action_import_order_manually(self):
        self.ensure_one()
        return {
            'name': _("Import Orders"),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'import.order.operation',
            'target': 'new',
            'context': {'default_channel_id': self.id, 'active_test': True}
        }

    def open_log_import_order(self):
        action = self._get_base_log_action()
        action.update({
            'domain': [('channel_id.id', '=', self.id), ('operation_type', '=', 'import_order')],
            'display_name': f'{self.name} - Logs - Order Import',
            'views': [
                (self.env.ref('omni_log.order_import_log_view_tree').id, 'list'),
                (self.env.ref('omni_log.order_import_log_view_form').id, 'form')
            ]
        })
        return action

    def open_log_import_shipment(self):
        action = self._get_base_log_action()
        action.update({
            'domain': [('channel_id.id', '=', self.id), ('operation_type', '=', 'import_shipment')],
            'display_name': f'{self.name} - Logs - Shipment Import',
            'views': [
                (self.env.ref('omni_log.shipment_import_log_view_tree').id, 'list'),
                (self.env.ref('omni_log.shipment_import_log_view_form').id, 'form')
            ]
        })
        return action

    def open_customer_groups(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('multichannel_order.action_customer_groups')
        action.update({
            'context': {'include_platform': True, 'default_channel_id': self.id},
            'target': 'main',
            'domain': [('channel_id.id', '=', self.id)],
            'display_name': '%s - Customer Groups' % self.name
        })
        return action

    def open_payment_gateways(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('multichannel_order.action_payment_gateways')
        action.update({
            'context': {'default_channel_id': self.id, 'include_platform': True},
            'target': 'main',
            'domain': [('channel_id.id', '=', self.id)],
            'display_name': '%s - Payment Gateways' % self.name
        })
        return action

    def _generate_action_order_view(self, view_ids):
        return {
            'name': f'{self.name} - Orders',
            'type': 'ir.actions.act_window',
            'domain': [('channel_id.id', '=', self.id)],
            'res_model': 'sale.order',
            'view_ids': view_ids,
            'search_view_id': self.env.ref('multichannel_order.view_store_sales_order_filter').id,
            'context': {
                'include_platform': True,
                'platform': self.platform,
            },
        }

    def create_order_menu(self, **kwargs):
        self.ensure_one()
        action_view_id = kwargs.get('action_view_id',
                                    self.env.ref('multichannel_order.view_all_store_orders_tree').id)
        view_ids = [(5, 0, 0), (0, 0, {'view_mode': 'tree', 'view_id': action_view_id})]

        cust_method_name = '%s_get_order_views' % self.platform
        if hasattr(self, cust_method_name):
            parent, view_ids = getattr(self, cust_method_name)()
        else:
            parent = self.env.ref('omni_manage_channel.menu_orders_root')

        parent.sudo().write({'active': True})

        action_values = self._generate_action_order_view(view_ids)

        action = self.env['ir.actions.act_window'].sudo().create(action_values)

        self.env['ir.model.data'].sudo().create({
            'name': 'action_{channel_id}'.format(channel_id=self.id),
            'module': 'multichannel_order',
            'model': action._name,
            'noupdate': True,
            'res_id': action.id,
        })
        values = {
            'parent_id': parent.id,
            'name': self.name,
            'sequence': 2,
            'action': 'ir.actions.act_window,%s' % str(action.id),
        }
        menu = self.env['ir.ui.menu'].sudo().create(values)
        self.env['ir.model.data'].sudo().create({
            'name': 'menu_{channel_id}'.format(channel_id=self.id),
            'module': 'multichannel_order',
            'model': menu._name,
            'noupdate': True,
            'res_id': menu.id,
        })
        self.with_context(for_channel_creation=True).sudo().write({'menu_order_id': menu.id})

    def _generate_default_order_process_rule_vals(self, statuses):
        self.ensure_one()
        vals = {
            'name': 'Default',
            'channel_id': self.id,
            'order_status_channel_ids': [(6, 0, statuses.ids)],
            'is_order_confirmed': True,
            'is_invoice_created': True,
            'is_payment_created': True,
        }
        return vals

    def create_order_process_rule(self):
        cust_method_name = '%s_get_default_order_statuses' % self.platform
        if hasattr(self, cust_method_name):
            statuses = getattr(self, cust_method_name)()
            vals = self._generate_default_order_process_rule_vals(statuses)
            self.env['order.process.rule'].sudo().create(vals)

    def set_default_payment_settings(self):
        journal = self.env['account.journal'].search([('type', 'in', ['bank', 'cash'])], limit=1)
        payment_method = journal.inbound_payment_method_line_ids[0].payment_method_id if journal.inbound_payment_method_line_ids else False
        deposit_account = self.env['account.account'].search([
                ('user_type_id', 'in', [self.env.ref('account.data_account_type_current_liabilities').id]),
                ('deprecated', '=', False),
                ('reconcile', '=', True),
            ], limit=1)
        self.update({
            'default_payment_journal_id': journal.id,
            'default_payment_method_id': payment_method.id,
            'default_deposit_account_id': deposit_account.id
        })

    def write(self, vals):
        """
        Override method to active/inactive order menus when doing active/inactive on store
        """
        res = super().write(vals)
        if 'active' in vals:
            self.mapped('menu_order_id').update({'active': vals['active']})
        return res

    @api.model
    def create(self, vals):
        """
        Override method to create menu, default order configuration and filters
        """
        record = super().create(vals)
        record._set_default_order_configuration()
        record.create_order_menu()
        record.set_default_payment_settings()
        record.create_order_process_rule()
        return record
