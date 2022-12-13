import json

from unittest.mock import patch, Mock
from .common import ignore_delay, no_commit
from odoo.addons.omni_manage_channel.tests.utils import get_data_path
from odoo.addons.multichannel_bigcommerce.tests.common import BigCommerceTestCommon, tagged
from ..utils.bigcommerce_customer_group_helper import BigcommerceCustomerGroupHelper
from odoo.addons.channel_base_sdk.utils.bigcommerce_api.resources.customer_group import DataInTrans
from odoo.addons.omni_manage_channel.tests.common import patch_request
from odoo.exceptions import ValidationError


@tagged('post_install', 'basic_test', '-at_install')
class TestBigCommerceCustomerGroup(BigCommerceTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(get_data_path(__file__, 'data/bigcommerce_get_customer_groups.json'), 'r') as fp:
            res_customer_group_json = json.load(fp)
        intrans = DataInTrans()
        cls.transformed_customer_groups = intrans(res_customer_group_json)
        cls.channel_category_1 = cls.env['product.channel.category'].create({
            'name': 'Unittest Bigcommerce Category',
            'channel_id': cls.bigcommerce_channel_1.id,
            'id_on_channel': 18
        })
        cls.customer_group_1 = cls.env['channel.customer.group'].create({
            'name': 'Bigcommerce Customer Group 1',
            'channel_id': cls.bigcommerce_channel_1.id,
            'has_all_categories_access': False,
            'categ_ids': [(6, 0, cls.channel_category_1.ids)]
        })

    @ignore_delay
    @no_commit
    def test_import_customer_groups(self):
        channel_customer_group = self.env['channel.customer.group']
        channel = self.bigcommerce_channel_1
        with patch('odoo.addons.multichannel_bigcommerce.utils.bigcommerce_customer_group_helper.BigCommerceCustomerGroupImporter.do_import', autospec=True) as mock_do_import:
            mock_do_import.return_value = [Mock(data=self.transformed_customer_groups[:1])]
            channel_customer_group.bigcommerce_get_data(channel_id=channel.id, all_records=True)
            categories = self.env['channel.customer.group'].search([('channel_id', '=', channel.id)])
            self.assertEqual(len(categories), 1)

            mock_do_import.return_value = [Mock(data=self.transformed_customer_groups)]
            channel_customer_group.bigcommerce_get_data(channel_id=channel.id, all_records=True)
            categories = self.env['channel.customer.group'].search([('channel_id', '=', channel.id)])
            self.assertEqual(len(categories), 2)

    def test_prepare_export_customer_group_to_bigcommerce(self):
        helper = BigcommerceCustomerGroupHelper(self.bigcommerce_channel_1)
        exporting_data = helper.prepare_data(self.customer_group_1)
        expected_data = {
            'name': 'Bigcommerce Customer Group 1',
            'category_access': 'specific',
            'categories': ['18']
        }
        self.assertEqual(expected_data, exporting_data)

    def test_create_customer_group_on_bigcommerce(self):
        with patch('odoo.addons.multichannel_bigcommerce.utils.bigcommerce_customer_group_helper.BigcommerceCustomerGroupHelper.create') as mock_create:
            self.customer_group_1._bigcommerce_export_customer_group()
            mock_create.assert_called_once()

    def test_update_customer_group_on_bigcommerce(self):
        self.customer_group_1.update({
            'id_on_channel': 7,
            'need_to_export': True
        })
        with patch('odoo.addons.multichannel_bigcommerce.utils.bigcommerce_customer_group_helper.BigcommerceCustomerGroupHelper.update') as mock_update:
            self.customer_group_1._bigcommerce_export_customer_group()
            mock_update.assert_called_once()

    def test_export_customer_group_process_successfully(self):
        export_res = {
            "id": 1,
            "name": "B2B",
            "is_default": False,
            "category_access": {
                "type": "all"
            },
            "discount_rules": [
                {
                    "type": "price_list",
                    "price_list_id": 1
                }
            ]
        }
        with patch_request(url=r'.*/customer_groups', jsn=export_res):
            self.customer_group_1._bigcommerce_export_customer_group()
            self.assertRecordValues(self.customer_group_1, [{
                'id_on_channel': '1',
            }])

    def test_export_customer_group_process_failed(self):
        export_res = {
            "status": 405,
            "title": "Method Not Allowed",
            "type": "https://developer.bigcommerce.com/api-docs/getting-started/api-status-codes",
            "detail": "The requested HTTP method is invalid for this endpoint."
        }
        with patch_request(url=r'.*/customer_groups', jsn=export_res, sts=405, rfs=True):
            with self.assertRaises(ValidationError):
                self.customer_group_1.bigcommerce_export_customer_group()
