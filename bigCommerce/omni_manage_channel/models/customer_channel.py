# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from operator import itemgetter
from itertools import groupby

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

global _phonenumbers_lib_warning
_phonenumbers_lib_warning = False

global _phonenumbers_lib_imported
_phonenumbers_lib_imported = False

try:
    import phonenumbers
    _phonenumbers_lib_imported = True

except ImportError:

    if not _phonenumbers_lib_warning:
        _logger.warning(
            "The `phonenumbers` Python module is not installed, contact look up will not be "
            "done for incoming calls. Try: pip install phonenumbers."
        )
        _phonenumbers_lib_warning = True

def format_phone(phone_number, country_code):
    if _phonenumbers_lib_imported and phone_number:
        try:
            phone_nbr = phonenumbers.parse(phone_number, region=country_code, keep_raw_input=True)
        except phonenumbers.phonenumberutil.NumberParseException:
            return phone_number
        if not phonenumbers.is_possible_number(phone_nbr) or not phonenumbers.is_valid_number(phone_nbr):
            return phone_number
        phone_fmt = phonenumbers.PhoneNumberFormat.INTERNATIONAL
        return phonenumbers.format_number(phone_nbr, phone_fmt)
    else:
        return phone_number


def compare_address(record, address, country_code='us'):
    """
    Compare existing address with the newly imported one
    :param models.Model record: Odoo record of model res.partner
    :param dict address: temporary data to be used for creating a new contact
    :return: True if the 2 addresses matched, False otherwise
    :rtype: bool
    """
    r, a = record, address  # Shorter aliases
    a['phone'] = format_phone(a['phone'], country_code)
    return (
        (r.name == a['name'] or not (r.name or a['name']))
        and (r.phone == a['phone'] or not (r.phone or a['phone']))
        and (r.email == a['email'] or not (r.email or a['email']))
        and (r.street == a['street_1'] or not (r.street or a['street_1']))
        and (r.street2 == a['street_2'] or not (r.street2 or a['street_2']))
        and (r.city == a['city'] or not (r.city or a['city']))
        and (r.zip == a['zip'] or not (r.zip or a['zip']))
        and (r.country_id.id == a['country_id'] or not (r.country_id.id or a['country_id']))
        and (r.state_id.id == a['state_id'] or not (r.state_id.id or a['state_id']))
    )


class CustomerChannel(models.Model):
    _name = 'customer.channel'
    _description = 'Customer Channel Info'

    id_on_channel = fields.Char(string='ID on Channel', index=True)
    channel_id = fields.Many2one('ecommerce.channel', string='Channel')
    name = fields.Char(string='Name')
    email = fields.Char(string='Email', index=True)
    phone = fields.Char(string='Phone')
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    zip = fields.Char(string='Zip')
    country_id = fields.Many2one('res.country', string='Country')
    state_id = fields.Many2one("res.country.state", string='State',
                               domain="[('country_id', '=?', country_id)]")

    display_address = fields.Text(string='Address', compute='_get_display_address')

    order_count = fields.Integer(compute='_compute_order_count')
    
    _sql_constraints = [
        ('id_on_channel_uniq', 'unique(id_on_channel, channel_id)', 'ID must be unique per Channel!'),
    ]

    def _compute_order_count(self):
        for record in self:
            order_count = self.env['sale.order'].sudo().search_count([('channel_id.id', '=', record.channel_id.id),
                                                  ('customer_channel_id.id', '=', record.id)]) or 0
            record.order_count = order_count
            
    def action_view_orders(self):
        self.ensure_one()
        tree_view_id = self.env.ref('sale.view_order_tree').id
        return {
            'name': _('Sales Orders'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'sale.order',
            'views': [(tree_view_id, 'tree'),(False, 'form')],
            'domain': [('channel_id.id', '=', self.channel_id.id),
                       ('customer_channel_id.id', '=', self.id)]
        }
        
    def _display_address(self):
        address_format = self.country_id.address_format \
                         or "%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s"
        args = {
            'state_code': self.state_id.code or '',
            'state_name': self.state_id.name or '',
            'country_code': self.country_id.code or '',
            'country_name': self.country_id.name or '',
        }
        for field in ('street', 'street2', 'zip', 'city', 'state_id', 'country_id'):
            args[field] = getattr(self, field) or ''

        return address_format % args

    def _get_display_address(self):
        for record in self:
            record.display_address = record._display_address()

    @api.model
    def create_jobs_for_synching(self, vals_list, channel_id):
        """
        Spit values list to smaller list and add to Queue Job
        :param vals_list:
        :param channel_id:
        :return:
        """
        start = 0
        step = 10
        uuids = []
        while start < len(vals_list):
            end = start + step
            pattern = vals_list[start:end]
            start = end
            uuids.append(self.with_delay()._sync_in_queue_job(pattern,
                                                              channel_id).uuid)
        return uuids

    @api.model
    def _sync_in_queue_job(self, customers, channel_id):
        """
        :param customers:
            Required list: the key should be id, name, phone, email
            Optional list: the key should be street, street2, city, state_id (int), country_id(int), zip
        :param channel_id (int): ID of current channel in Odoo
        :return:
        """

        def _prepare_data(customers_data, new_customers=True):
            vals_list = []
            for c in customers_data:
                vals = {
                    'name': c['name'],
                    'phone': c.get('phone', ''),
                    'email': c['email'],
                    'channel_id': channel_id,
                    'id_on_channel': str(c['id']) if str(c['id']) != '0' else False,
                    'street': c.get('street', ''),
                    'street2': c.get('street2', ''),
                    'city': c.get('city', ''),
                    'state_id': c.get('state_id', False),
                    'country_id': c.get('country_id', False),
                    'zip': c.get('zip', '')
                }
                vals_list.append(vals)
            return vals_list

        record_ids = []
        # Only create new customers from each channel
        ids = [str(c['id']) for c in customers]
        existed_customers = self.env['customer.channel'].sudo().search(
            [('id_on_channel', 'in', ids), ('channel_id.id', '=', channel_id), ('id_on_channel', '!=', '0')])

        guest_customers = list(filter(lambda c: str(c['id']) == '0', customers))
        comparing_list = list()
        for customer in guest_customers:
            for f in ('email', 'name', 'phone', 'street', 'city', 'zip'):
                # Any address must have at least one of these fields
                # If not, it is not worth to be recorded
                if customer.get(f):
                    comparing_list.append((f, customer[f]))
                    break
        if comparing_list:
            country_codes = self.env['res.country'].sudo().search_read(
                [('id', 'in', [add.get('country_id') for add in customers if add])],
                ['id', 'code']
            )
            country_codes = {cc['id']: cc['code'] for cc in country_codes}

            guest_domain = [(f, 'in', tuple(map(itemgetter(1), values)))
                            for f, values in groupby(sorted(comparing_list, key=itemgetter(0)), key=itemgetter(0))]
            guest_domain = [('channel_id.id', '=', channel_id)] + ['|'] * (len(guest_domain) - 1) + guest_domain
            potential_customers = self.env['customer.channel'].sudo().search(guest_domain)
            for customer in guest_customers:
                compared = {**customer, **{
                    'street_1': customer.get('street') or False,
                    'street_2': customer.get('street2') or False,
                }}
                existed_customers |= potential_customers.filtered(
                    lambda c: compare_address(c, compared, country_codes.get(compared.get('country_id')) or 'US'))

        existed_ids = existed_customers.mapped('id_on_channel')
        new_customers = list(filter(lambda c: str(c['id']) not in existed_ids, customers))

        vals_list = _prepare_data(new_customers)
        newly_created_customers = self.create(vals_list)
        record_ids.extend(newly_created_customers.ids)

        if existed_customers:
            for existed_customer in existed_customers.filtered(lambda r: r.id_on_channel != '0'):
                customer_data = list(filter(lambda c: str(c['id']) == existed_customer.id_on_channel, customers))
                if customer_data:
                    vals = _prepare_data(customer_data, new_customers=False)[0]
                    existed_customer.with_context(for_synching=True).sudo().write(vals)
            record_ids.extend(existed_customers.ids)

        return record_ids

    @api.model
    def create(self, vals):
        if 'phone' in vals:
            country_code = None
            if 'country_id' in vals:
                country_code = self.env['res.country'].sudo().browse(vals['country_id']).code
            if 'phone' in vals and vals['phone']:
                vals['phone'] = format_phone(phone_number=vals['phone'], country_code=country_code)
        return super(CustomerChannel, self).create(vals)

    def write(self, vals):
        res = super(CustomerChannel, self).write(vals)
        if 'update_phone' not in self.env.context:
            for record in self:
                if 'phone' in vals and vals['phone']:
                    country_code = None
                    if record.country_id:
                        country_code = record.country_id.code
                    record.sudo().with_context(update_phone=True).write(
                        {'phone': format_phone(phone_number=vals['phone'],
                                               country_code=country_code)})
        return res

class ResPartner(models.Model):
    _inherit = "res.partner"

    def _get_default_country_id(self):
        return self.env.ref('base.us').id

    country_id = fields.Many2one(default=_get_default_country_id)

    def _get_contact_name(self, partner, name):
        if not partner.sudo().parent_id.is_company and not partner.commercial_company_name:
            return name
        return super(ResPartner, self)._get_contact_name(partner, name)

    @api.model
    def _get_address_format(self):
        format = super(ResPartner, self)._get_address_format()
        if self and self.country_id.code == 'US':
            format = "%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s"
        return format

    @api.model
    def get_customer_partner(self, customer_data):
        if not customer_data['name']:
            return self
        partner = self.sudo().search([('type', '=', 'contact'), ('email', '=', customer_data['email']), ('email', '!=', False)], limit=1)
        if not partner:
            vals = {'name': customer_data['name'],
                    'phone': customer_data.get('phone', ''),
                    'email': customer_data['email'],
                    'street': customer_data.get('street', ''),
                    'street2': customer_data.get('street2', ''),
                    'city': customer_data.get('city', ''),
                    'state_id': customer_data.get('state_id', False),
                    'country_id': customer_data.get('country_id', False),
                    'zip': customer_data.get('zip', ''),
                    'type': 'contact',
                    'customer_rank': 1
                    }
            partner = self.sudo().with_context(mail_create_nosubscribe=True).create(vals)
        return partner

    @api.model
    def get_shipping_address(self, domain):
        """
        Get shipping address on that customer. Used in creating delivery order
        The list of key must have in domain is name, street, street2, city, zip, country_code, state, email and phone
        :param domain:
        :return:
        """
        shipping_addresses = self.child_ids.filtered(lambda c: c.type == 'delivery'
                                                               and c.name == domain['name']
                                                               and c.street == domain['street']
                                                               and c.street2 == domain['street2']
                                                               and c.city == domain['city']
                                                               and c.state_id.name == domain['state']
                                                               and c.zip == domain['zip']
                                                               and c.country_id.code == domain['country_code']
                                                               and c.email == domain['email']
                                                               and c.phone == domain['phone'])

        if not shipping_addresses:
            return self
        return shipping_addresses[0]

    @api.model
    def create(self, vals):
        if 'phone' in vals:
            country_code = None
            if 'country_id' in vals:
                country_code = self.env['res.country'].sudo().browse(vals['country_id']).code
            if 'phone' in vals and vals['phone'] and type(vals['phone']) == str and country_code:
                try:
                    vals['phone'] = format_phone(phone_number=vals['phone'], country_code=country_code)
                except:
                    _logger.exception("Error in formatting phone number!")
        return super(ResPartner, self).create(vals)

    def write(self, vals):
        res = super(ResPartner, self).write(vals)
        if 'update_phone' not in self.env.context:
            for record in self:
                if 'phone' in vals and vals['phone']:
                    country_code = None
                    if record.country_id:
                        country_code = record.country_id.code
                    record.sudo().with_context(update_phone=True).write({'phone': format_phone(phone_number=vals['phone'],
                                                                                               country_code=country_code)})
        return res
