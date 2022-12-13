# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from .common import ChannelOrderTestCommon, tagged
from unittest.mock import patch
from .common import ignore_delay, no_commit

@tagged('post_install', 'basic_test', '-at_install')
class TestExportProduct(ChannelOrderTestCommon):
        
    @ignore_delay
    @no_commit
    def test_export_log_export_master(self):
        wizard = self.env['export.product.composer'].create({
            'product_tmpl_id': self.test_data['master_1'].id,
            'channel_id': self.test_data['store_1'].id
        })
        with patch('odoo.addons.multichannel_product.models.product_channel.ProductChannel._push_to_channel', autospec=True) as mock_push_action:
            with patch('odoo.addons.multichannel_product.models.product_channel.ProductChannel._put_to_channel', autospec=True) as mock_put_action:
                datas = {'name': 'Listing Name'}
                mock_push_action.return_value = datas
                action = wizard.with_context(job_uuid='12312312321').export()
                product_mapping = self.env['product.channel'].browse(action['res_id'])
                log = self.env['omni.log'].search([('job_uuid', '=', '12312312321')])
                self.assertRecordValues(log, [{'datas': datas, 
                                                'channel_id': product_mapping.channel_id.id,
                                                'operation_type': 'export_master',
                                                'res_model': 'product.template',
                                                'res_id': product_mapping.product_tmpl_id.id,
                                                'entity_name': product_mapping.display_name,
                                                'job_uuid': '12312312321',
                                                'status': 'done'
                                            }])
                
    @ignore_delay
    @no_commit
    def test_export_log_export_mapping(self):
        wizard = self.env['export.product.composer'].create({
            'product_tmpl_id': self.test_data['master_1'].id,
            'channel_id': self.test_data['store_1'].id
        })
        with patch('odoo.addons.multichannel_product.models.product_channel.ProductChannel._push_to_channel', autospec=True) as mock_push_action:
            with patch('odoo.addons.multichannel_product.models.product_channel.ProductChannel._put_to_channel', autospec=True) as mock_put_action:
                datas = {'name': 'Listing Name'}
                mock_push_action.return_value = datas
                action = wizard.export()
                product_mapping = self.env['product.channel'].browse(action['res_id'])
                mock_put_action.return_value = datas
                product_mapping.with_context(job_uuid='12312312321').export_from_mapping()
                log = self.env['omni.log'].search([('job_uuid', '=', '12312312321')])
                self.assertRecordValues(log, [{'datas': datas, 
                                            'channel_id': product_mapping.channel_id.id,
                                            'operation_type': 'export_mapping',
                                            'res_model': product_mapping._name,
                                            'entity_name': product_mapping.display_name,
                                            'status': 'done',
                                            'job_uuid': '12312312321',
                                            }])
        