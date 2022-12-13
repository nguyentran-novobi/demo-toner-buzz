# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
from odoo import api, models, _
from odoo.addons.omni_manage_channel.models.customer_channel import compare_address


class CustomerChannel(models.Model):
    _inherit = 'customer.channel'
    
    @api.model
    def get_data_from_channel(self, channel_id, id_on_channel, customer_data: dict = None) -> list:
        """
        If `customer_data` is provided, create profile from that data
        If not, then `id_on_channel` will be used to fetch profile data from channel
        Return list of customer.channel ids in Odoo
        """
        if not customer_data:
            channel = self.env['ecommerce.channel'].sudo().browse(channel_id)
            cust_method_name = '{platform}_get_data'.format(platform=channel.platform)
            if hasattr(self, cust_method_name):
                return getattr(self, cust_method_name)(channel_id=channel_id, id_on_channel=id_on_channel, async_load=False)
            return []
        return self._sync_in_queue_job([customer_data], channel_id)

    def determine_company(self, vals, country_code):
        compared = {**vals, **{
            'street_1': vals.get('street') or False,
            'street_2': vals.get('street2') or False,
        }}
        
        companies = self.env['res.partner'].sudo().search([('name', '=', vals['company']),
                                                           ('is_company', '=', True)])
        companies.filtered(
            lambda r: (compare_address(r, {**compared, **dict(name=vals['company'])}, country_code)))
        if not companies:
            # Use address on billing or shipping to create company
            # Delete key for creating record
            new_vals = {**vals, **dict(name=vals['company'], is_company=True)}
            if 'company' in new_vals:
                del new_vals['company']
            company = self.env['res.partner'].sudo(). \
                with_context(mail_create_nosubscribe=True).create(new_vals)
        else:
            company = companies[0]
        return company

    def determine_customer(self, channel, invoice_info, shipping_info, order_number):
        assert len(self) <= 1, 'Customer generating method is supposed to run with no or only one customer'
        # Prepare Customer Channel and the main contact
        parent = self.env['res.partner'].browse()
        if len(self) != 0:
            # This customer is not a guest
            customer_data = {
                'name': self.name,
                'phone': self.phone,
                'email': self.email,
                'channel_id': channel.id,
                'id_on_channel': self.id_on_channel,
                'street': self.street,
                'street2': self.street2,
                'city': self.city,
                'state_id': self.state_id.id,
                'country_id': self.country_id.id,
                'zip': self.zip
            }
            parent = self.env['res.partner'].get_customer_partner(customer_data)
        elif invoice_info:
            # If this customer is a guest, we will use invoice info to create customer if possible
            parent = self.env['res.partner'].get_customer_partner(invoice_info)
        elif shipping_info:
            # If this customer is a guest, we will use shipping info to create customer if possible
            parent = self.env['res.partner'].get_customer_partner(shipping_info)

        customer_channel = self
        if not parent:
            parent = self.env['res.partner'].create({
                'name': f"{channel.default_guest_customer} {order_number}",
                'type': 'contact'
            })

        # Generate sub-contacts if needed
        contact_types = ('invoice', 'delivery')
        addresses = (invoice_info, shipping_info)
        contacts = ()
        empty_contact = self.env['res.partner'].browse()

        country_codes = self.env['res.country'].sudo().search_read(
            [('id', 'in', [add['country_id'] for add in addresses if add and add['country_id']])],
            ['id', 'code']
        )
        country_codes = {cc['id']: cc['code'] for cc in country_codes}
        for address, contact_type in zip(addresses, contact_types):
            matching = None
            if address:
                if address['name'] != '':
                    company = empty_contact
                    compared = {**address, **{
                        'street_1': address.get('street') or False,
                        'street_2': address.get('street2') or False,
                    }}
                    if 'company' in address and address['company']:
                        company = self.determine_company(address, country_codes.get(compared['country_id']) or 'US')

                    parent_id = company.id or parent.id
                    # Find matching sub-contact
                    if company:
                        matching = company.child_ids.filtered(lambda r: (
                            r.type == contact_type
                            and compare_address(r, compared, country_codes.get(compared['country_id']) or 'US')
                        ))
                    else:
                        matching = parent.child_ids.filtered(lambda r: (
                                r.type == contact_type
                                and compare_address(r, compared, country_codes.get(compared['country_id']) or 'US')
                        ))
                else:
                    matching = channel.default_guest_customer
                if matching:
                    matching = matching[0]
                address['parent_id'] = parent_id
                # Delete key for creating record
                if 'company' in address:
                    del address['company']
            contacts += (matching or address or parent,)
        if any(map(lambda a: isinstance(a, dict), contacts)):
            # If there is any available info, new sub-contacts are created
            # Or use the matching record or leave it empty
            records = empty_contact.with_context(mail_create_nosubscribe=True).create(list(filter(lambda a: isinstance(a, dict), contacts)))
            contacts = tuple(records.filtered(lambda r: r.type == t) or c or parent
                             for t, c in zip(contact_types, contacts))

        return (customer_channel, parent) + contacts
