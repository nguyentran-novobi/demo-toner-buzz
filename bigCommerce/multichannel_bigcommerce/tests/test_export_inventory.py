# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo.addons.multichannel_bigcommerce.tests.common import BigCommerceTestCommon, tagged
from unittest.mock import patch
from .common import ignore_delay, no_commit
import logging
import copy

@tagged('post_install', 'basic_test', '-at_install')
class TestExportInventory(BigCommerceTestCommon):
        
    @ignore_delay
    @no_commit
    @patch('odoo.addons.multichannel_bigcommerce.models.ecommerce_channel.BigCommerceChannel._bigcommerce_sync_inventory')
    @patch('odoo.addons.multichannel_bigcommerce.models.ecommerce_channel.BigCommerceChannel._bigcommerce_prepare_exported_inventory_data')
    def test_export_log_export_inventory(self, mock_prepare_data, mock_sync):
        data_sync = []
        for i in range(0, 20):
            data_sync.append({
                            'id': '1232324',
                            'inventory_tracking': 'variant',
                            'variants': [],
                            'res_id': i
                        })
        mock_prepare_data.return_value = copy.deepcopy(data_sync)
        uuids = self.bigcommerce_channel_1._bigcommerce_update_inventory([])
        logs = self.env['omni.log'].search([('job_uuid', 'in', uuids)])
        compared_vals = []
        def divide_chunks():
            for i in range(0, len(data_sync), 9): 
                yield data_sync[i:i + 9]
        datas = divide_chunks()
        self.assertEqual(len(logs), len(list(datas)))
        