# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import functools
import uuid

from datetime import datetime
from unittest.mock import patch, Mock

from odoo.tests.common import tagged

from odoo.addons.omni_manage_channel.tests.common import ListingTestCommon


class NonDelayableRecordset:
    def __init__(self, recordset):
        self.recordset = recordset

    def __getattr__(self, name):
        if name in self.recordset:
            raise AttributeError
        recordset_method = getattr(self.recordset, name)

        def exe(*args, **kwargs):
            recordset_method(*args, **kwargs)
            return Mock(uuid=str(uuid.uuid4()))

        return exe


def ignore_delay(func):
    def with_delay_side_effect(self, *_args, **_kwargs):
        return NonDelayableRecordset(self)

    @functools.wraps(func)
    def wrapper_ignore_delay(*args, **kwargs):
        with patch('odoo.addons.queue_job.models.base.Base.with_delay',
                   side_effect=with_delay_side_effect, autospec=True):
            res = func(*args, **kwargs)
        return res
    return wrapper_ignore_delay


def no_commit(func):
    @functools.wraps(func)
    def no_commit_wrapper(*args, **kwargs):
        with patch('odoo.sql_db.Cursor.commit', autospec=True):
            res = func(*args, **kwargs)
        return res
    return no_commit_wrapper


@tagged('post_install', 'basic_test', '-at_install')
class ChannelOrderTestCommon(ListingTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._add_status()
        cls._add_channels()
        cls._add_products()
        cls._add_customers()
        cls._add_listings()
        cls._add_orders()
        
    @classmethod
    def _add_status(cls):
        imported_status = cls.env['order.status.channel'].create({'id_on_channel': '1', 
                                                                  'name': 'Test', 
                                                                  'platform': 'none'})
        cls.test_data.update({'imported_status_id': imported_status.id})
    
    @classmethod
    def _add_channels(cls):
        test_data = cls.test_data
        ecommerce_channel_model = cls.env['ecommerce.channel']

        store_1 = ecommerce_channel_model.create({
            'name': 'Test Store',
            'platform': False,
            'active': True,
        })
        store_2 = ecommerce_channel_model.create({
            'name': 'Test Store',
            'platform': False,
            'active': True,
            'auto_create_master_product': False
        })

        test_data.update({
            'store_1': store_1,
            'store_2': store_2,
        })
        
    @classmethod
    def _add_products(cls):
        # Product Categories
        product_category_model = cls.env['product.category']
        categ_1 = product_category_model.create({
            'name': 'Category 1',
        })
        categ_2 = product_category_model.create({
            'name': 'Category 2',
        })

        product_product_model = cls.env['product.product']

        # Products
        consum_1 = product_product_model.create({
            'name': 'Consumable 1',
            'categ_id': categ_1.id,
            'standard_price': 250.0,
            'list_price': 280.0,
            'type': 'consu',
            'weight': 0.01,
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
            'uom_po_id': cls.env.ref('uom.product_uom_unit').id,
            'default_code': 'consu-1',
            'invoice_policy': 'order',
            'expense_policy': 'no',
            'taxes_id': [(6, 0, [])],
            'supplier_taxes_id': [(6, 0, [])],
        })
        consum_2 = product_product_model.create({
            'name': 'Consumable 2',
            'categ_id': categ_2.id,
            'standard_price': 1050.0,
            'list_price': 1100.0,
            'type': 'consu',
            'weight': 0.1,
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
            'uom_po_id': cls.env.ref('uom.product_uom_unit').id,
            'default_code': 'consu-2',
            'invoice_policy': 'order',
            'expense_policy': 'no',
            'taxes_id': [(6, 0, [])],
            'supplier_taxes_id': [(6, 0, [])],
        })
        serv_1 = product_product_model.create({
            'name': 'Service 1',
            'categ_id': categ_1.id,
            'standard_price': 5045.0,
            'list_price': 5055.0,
            'type': 'service',
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
            'uom_po_id': cls.env.ref('uom.product_uom_unit').id,
            'default_code': 'service-1',
            'service_type': 'manual',
            'invoice_policy': 'order',
            'expense_policy': 'no',
            'taxes_id': [(6, 0, [])],
            'supplier_taxes_id': [(6, 0, [])],
        })
        serv_2 = product_product_model.create({
            'name': 'Service 2',
            'categ_id': categ_2.id,
            'standard_price': 9330.0,
            'list_price': 9440.0,
            'type': 'service',
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
            'uom_po_id': cls.env.ref('uom.product_uom_unit').id,
            'default_code': 'service-2',
            'service_type': 'manual',
            'invoice_policy': 'order',
            'expense_policy': 'no',
            'taxes_id': [(6, 0, [])],
            'supplier_taxes_id': [(6, 0, [])],
        })
        prod_1 = product_product_model.create({
            'name': 'Product 1',
            'categ_id': categ_1.id,
            'standard_price': 175.0,
            'list_price': 180.0,
            'type': 'product',
            'weight': 0.3,
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
            'uom_po_id': cls.env.ref('uom.product_uom_unit').id,
            'default_code': 'prod-1',
            'invoice_policy': 'order',
            'expense_policy': 'no',
            'taxes_id': [(6, 0, [])],
            'supplier_taxes_id': [(6, 0, [])],
        })
        prod_2 = product_product_model.create({
            'name': 'Product 2',
            'categ_id': categ_2.id,
            'standard_price': 230.0,
            'list_price': 245.0,
            'type': 'product',
            'weight': 0.7,
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
            'uom_po_id': cls.env.ref('uom.product_uom_unit').id,
            'default_code': 'prod-2',
            'invoice_policy': 'order',
            'expense_policy': 'no',
            'taxes_id': [(6, 0, [])],
            'supplier_taxes_id': [(6, 0, [])],
        })

        cls.test_data.update({
            'categ_1': categ_1,
            'categ_2': categ_2,
            'consum_1': consum_1,
            'consum_2': consum_2,
            'serv_1': serv_1,
            'serv_2': serv_2,
            'prod_1': prod_1,
            'prod_2': prod_2,
        })

    @classmethod
    def _add_customers(cls):
        res_partner_model = cls.env['res.partner']

        # Contacts
        # Partner with the same main and sub-contacts
        partner_us_1_data = {
            'name': 'Heather A Flynn',
            'phone': '+1 917-248-2381',
            'email': 'heather.flynn@auto-test.test',
            'street': '3251 Francis Mine',
            'street2': 'Apt 211',
            'city': 'Huletts Landing',
            'state_id': cls.env.ref('base.state_us_27').id,  # New York
            'country_id': cls.env.ref('base.us').id,  # USA
            'zip': '12841',
        }
        main_contact_us_1 = res_partner_model.create({**partner_us_1_data, **{
            'type': 'contact',
            'customer_rank': 1,
        }})
        billing_address_us_1 = res_partner_model.create({**partner_us_1_data, **{
            'type': 'invoice',
            'parent_id': main_contact_us_1.id,
        }})
        shipping_address_us_1 = res_partner_model.create({**partner_us_1_data, **{
            'type': 'delivery',
            'parent_id': main_contact_us_1.id,
        }})

        # Partner with different main and sub-contacts
        partner_us_2_data_1 = {
            'name': 'Matthew T Domino',
            'phone': '+1 415-877-3664',
            'email': 'matthew.domino@auto-test.test',
            'street': '3914 Roosevelt Street',
            'street2': 'PO. Box 5441',
            'city': 'Mill Valley',
            'state_id': cls.env.ref('base.state_us_5').id,  # California
            'country_id': cls.env.ref('base.us').id,  # USA
            'zip': '94941',
        }
        partner_us_2_data_2 = {
            'name': 'Lillian D Thompson',
            'phone': '+1 509-378-3903',
            'email': 'lillian.thompson@auto-test.test',
            'street': '1756 Goodwin Avenue',
            'street2': 'R24',
            'city': 'Spokane Valley',
            'state_id': cls.env.ref('base.state_us_48').id,  # Washington
            'country_id': cls.env.ref('base.us').id,  # USA
            'zip': '99206',
        }
        main_contact_us_2 = res_partner_model.create({**partner_us_2_data_1, **{
            'type': 'contact',
            'customer_rank': 1,
        }})
        billing_address_us_2 = res_partner_model.create({**partner_us_2_data_1, **{
            'type': 'invoice',
            'parent_id': main_contact_us_2.id,
        }})
        shipping_address_us_2 = res_partner_model.create({**partner_us_2_data_2, **{
            'type': 'delivery',
            'parent_id': main_contact_us_2.id,
        }})

        cls.shared_data.update({
            'partner_us_1_data': partner_us_1_data,
            'partner_us_2_data_1': partner_us_2_data_1,
            'partner_us_2_data_2': partner_us_2_data_2,
        })
        cls.test_data.update({
            'main_contact_us_1': main_contact_us_1,
            'billing_address_us_1': billing_address_us_1,
            'shipping_address_us_1': shipping_address_us_1,
            'main_contact_us_2': main_contact_us_2,
            'billing_address_us_2': billing_address_us_2,
            'shipping_address_us_2': shipping_address_us_2,
        })

    @classmethod
    def _add_listings(cls):
        mapping_model = cls.env['product.channel']
        listing_1_vals = {
            'name': 'Listing 1',
            'id_on_channel': 'LISTING01',
            'default_code': cls.test_data['prod_1'].product_tmpl_id.default_code,
            'channel_id': cls.test_data['store_1'].id,
            'product_tmpl_id': cls.test_data['prod_1'].product_tmpl_id.id,
            'product_variant_ids': [(0, 0, {'id_on_channel': 'LISTING01-VARIANT-1',
                                            'product_product_id': cls.test_data['prod_1'].id,
                                            'default_code': cls.test_data['prod_1'].default_code})]
        }
        listing_1 = mapping_model.create(listing_1_vals)
        
        listing_2_vals = {
            'name': 'Listing 2',
            'id_on_channel': 'LISTING02',
            'default_code': cls.test_data['prod_2'].product_tmpl_id.default_code,
            'channel_id': cls.test_data['store_1'].id,
            'product_tmpl_id': cls.test_data['prod_2'].product_tmpl_id.id,
            'product_variant_ids': [(0, 0, {'id_on_channel': 'LISTING02-VARIANT-1',
                                            'product_product_id': cls.test_data['prod_2'].id,
                                            'default_code': cls.test_data['prod_2'].default_code})]
        }
        listing_2 = mapping_model.create(listing_2_vals)
        
        cls.test_data.update({
            'listing_1': listing_1,
            'listing_2': listing_2
        })
        
    @classmethod
    def _add_orders(cls):
        lines = [{
            'product_id': 'LISTING01',
            'sku': 'prod-1',
            'variant_id': 'LISTING01-VARIANT-1',
            'id_on_channel': 'LINE1',
            'quantity': 1,
            'name': 'LISTING01-VARIANT-1',
            'price': 10.0
        }]
        order_data_1 = {
            'name': 'ORDER1',
            'lines': lines,
            'customer_id': 0,
            'id': 'ORDER01',
            'channel_date_created': datetime.now(),
            'payment_method': 'Cash',
            'channel_order_ref': 'ORDER01',
            'status_id': 1
        }
        
        lines_2 = [{
            'product_id': 'LISTING03',
            'sku': 'prod-5',
            'variant_id': 'LISTING03-VARIANT-1',
            'id_on_channel': 'LINE1',
            'quantity': 1,
            'name': 'LISTING03-VARIANT-1',
            'price': 10.0
        }]
        order_data_2 = {
            'name': 'ORDER1',
            'lines': lines_2,
            'customer_id': 0,
            'id': 'ORDER01',
            'channel_date_created': datetime.now(),
            'payment_method': 'Cash',
            'channel_order_ref': 'ORDER02',
            'status_id': 1
        }
        cls.test_data.update({
            'order_data_1': order_data_1,
            'order_data_2': order_data_2
        })
