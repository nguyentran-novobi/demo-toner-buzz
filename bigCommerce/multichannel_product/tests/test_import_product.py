# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from .common import ChannelOrderTestCommon, tagged
from unittest.mock import patch
from .common import ignore_delay, no_commit


@tagged('post_install', 'basic_test', '-at_install')
class TestImportProduct(ChannelOrderTestCommon):
        
    @ignore_delay
    @no_commit
    @patch('odoo.addons.multichannel_product.models.product_template.ProductTemplate._sync_in_queue_job')
    def test_create_log_import_product(self, mock_create_product):
        product_template_model = self.env['product.template']
        data = self.test_data['mapping_data_1']
        store = self.test_data['store_1']
        job_uuids = product_template_model.create_jobs_for_synching([data], store.id)
        logs = self.env['omni.log'].search([('job_uuid', 'in', job_uuids)])
        self.assertRecordValues(logs, [{'datas': data, 
                                        'channel_id': store.id,
                                        'operation_type': 'import_product',
                                        'res_model': 'product.channel',
                                        'entity_name': data['name'],
                                        'product_sku': data.get('sku'),
                                        'status': 'draft',
                                        'channel_record_id': str(data['id'])}])
        mock_create_product.assert_called_once()
        