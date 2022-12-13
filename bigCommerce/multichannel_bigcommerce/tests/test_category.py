import json


from unittest.mock import patch, Mock
from .common import ignore_delay, no_commit
from ..utils.bigcommerce_category_helper import BigcommerceCategoryHelper
from odoo.addons.omni_manage_channel.tests.utils import get_data_path
from odoo.addons.multichannel_bigcommerce.tests.common import BigCommerceTestCommon, tagged
from odoo.addons.channel_base_sdk.utils.bigcommerce_api.resources.category_tree import DataInTrans as CategoryTreeDataInTrans
from odoo.addons.channel_base_sdk.utils.bigcommerce_api.resources.category import DataInTrans as CategoryDetailDataInTrans
from odoo.addons.omni_manage_channel.tests.common import patch_request
from odoo.exceptions import ValidationError


@tagged('post_install', 'basic_test', '-at_install')
class TestBigCommerceImportCategory(BigCommerceTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(get_data_path(__file__, 'data/bigcommerce_get_tree_categories.json'), 'r') as fp:
            res_tree_categories_json = json.load(fp)
        with open(get_data_path(__file__, 'data/bigcommerce_get_detail_categories.json'), 'r') as fp:
            res_detail_categories = json.load(fp)

        category_tree_intrans = CategoryTreeDataInTrans()
        category_detail_intrans = CategoryDetailDataInTrans()
        cls.transformed_tree_categories = category_tree_intrans(res_tree_categories_json)
        cls.transformed_detail_categories = category_detail_intrans(res_detail_categories)
        cls.bigcommerce_channel_1.default_categ_id.update({
            'url': 'bigcommerce/url/1',
            'description': 'Bigcommerce Category',
            'sort_order': 3,
            'image_url': 'bigcommerce/image/1',
            'page_title': 'Bigcommerce Title',
            'meta_keywords': '123, 456',
            'search_keywords': 'Bigcommerce search keywords',
            'meta_description': 'Bigcommerce meta description'
        })

    @ignore_delay
    def test_import_categories(self):
        product_channel_category = self.env['product.channel.category']
        channel = self.bigcommerce_channel_1
        with patch('odoo.addons.multichannel_bigcommerce.utils.bigcommerce_category_helper.BigCommerceCategoryImporter.do_tree_import', autospec=True) as mock_do_tree_import, \
                patch('odoo.addons.multichannel_bigcommerce.utils.bigcommerce_category_helper.BigCommerceCategoryImporter.do_detail_import', autospec=True) as mock_do_detail_import:
            mock_do_tree_import.return_value = Mock(data=self.transformed_tree_categories[:4])
            mock_do_detail_import.return_value = [Mock(data=self.transformed_detail_categories[:5])]
            product_channel_category.bigcommerce_get_data(channel_id=channel.id, all_records=True)
            categories = self.env['product.channel.category'].search([('channel_id', '=', channel.id)])
            # bigcommerce_channel_1 has 1 default category -> 1 + 5 = 6
            self.assertEqual(len(categories), 6)

            mock_do_tree_import.return_value = Mock(data=self.transformed_tree_categories)
            mock_do_detail_import.return_value = [Mock(data=self.transformed_detail_categories)]
            product_channel_category.bigcommerce_get_data(channel_id=channel.id, all_records=True)
            categories = self.env['product.channel.category'].search([('channel_id', '=', channel.id)])
            # bigcommerce_channel_1 has 1 default category -> 1 + 6 = 7
            self.assertEqual(len(categories), 7)

    def test_export_category_to_bigcommerce(self):
        helper = BigcommerceCategoryHelper(self.bigcommerce_channel_1)
        exporting_data = helper.prepare_data(self.bigcommerce_channel_1.default_categ_id)
        expected_data = {
            'name': 'Tmp',
            'url': 'bigcommerce/url/1',
            'parent_id': 0,
            'description': 'Bigcommerce Category',
            'sort_order': 3,
            'default_product_sort': 'use_store_settings',
            'image_url': '',
            'page_title': 'Bigcommerce Title',
            'meta_keywords': ['123', '456'],
            'search_keywords': 'Bigcommerce search keywords',
            'meta_description': 'Bigcommerce meta description',
            'is_visible': True
        }
        self.assertEqual(expected_data, exporting_data)

    def test_export_category_process_successfully(self):
        export_res = {
          "data": [
            {
              "id": 19,
              "parent_id": 0,
              "name": "Garden",
              "description": "<p>This is the garden description</p>",
              "views": 0,
              "sort_order": 2,
              "page_title": "page title",
              "meta_keywords": [
                "meta keyword"
              ],
              "meta_description": "meta description",
              "layout_file": "category.html",
              "image_url": "",
              "is_visible": True,
              "search_keywords": "search keywords",
              "default_product_sort": "use_store_settings",
              "custom_url": {
                "url": "/garden/",
                "is_customized": False
              }
            },
          ],
          "meta": {
            "pagination": {
              "total": 1,
              "count": 1,
              "per_page": 50,
              "current_page": 1,
              "total_pages": 1,
              "links": {
                "current": "?page=1&limit=50"
              }
            }
          }
        }
        with patch_request(url=r'.*/categories', jsn=export_res):
            self.bigcommerce_channel_1.default_categ_id.bigcommerce_export_category()
            self.assertRecordValues(self.bigcommerce_channel_1.default_categ_id, [{
                'id_on_channel': '19',
            }])

    def test_export_category_process_failed(self):
        export_res = {
            "status": 405,
            "title": "Method Not Allowed",
            "type": "https://developer.bigcommerce.com/api-docs/getting-started/api-status-codes",
            "detail": "The requested HTTP method is invalid for this endpoint."
        }
        with patch_request(url=r'.*/categories', jsn=export_res, sts=405, rfs=True):
            with self.assertRaises(ValidationError):
                self.bigcommerce_channel_1.default_categ_id.bigcommerce_export_category()
