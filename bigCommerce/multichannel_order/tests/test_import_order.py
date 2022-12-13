# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from .common import ChannelOrderTestCommon, tagged
from unittest.mock import patch
from .common import ignore_delay, no_commit

@tagged('post_install', 'basic_test', '-at_install')
class TestImportOrder(ChannelOrderTestCommon):
        
    @ignore_delay
    @no_commit
    @patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder._prepare_imported_order')
    @patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder._sync_in_queue_job')
    def test_process_order_data(self, mock_create_order, mock_prepare_data):
        sale_order_model = self.env['sale.order']
        store = self.test_data['store_1']
        order_data = self.test_data['order_data_1']
        mock_prepare_data.return_value = order_data
        sale_order_model.create_jobs_for_synching([order_data], store.id)        
        mock_create_order.assert_called_once()
        
    @ignore_delay
    @no_commit
    @patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder._prepare_imported_order')
    @patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder._sync_in_queue_job')
    def test_create_log_import_order(self, mock_create_order, mock_prepare_data):
        sale_order_model = self.env['sale.order']
        store = self.test_data['store_1']
        order_data = self.test_data['order_data_1']
        mock_prepare_data.return_value = order_data
        job_uuids = sale_order_model.create_jobs_for_synching([order_data], store.id)
        logs = self.env['omni.log'].search([('job_uuid', 'in', job_uuids)])
        self.assertRecordValues(logs, [{'datas': order_data, 
                                        'status': 'draft',
                                        'job_uuid': job_uuids[0],
                                        'channel_id': store.id,
                                        'operation_type': 'import_order',
                                        'entity_name': order_data['channel_order_ref'],
                                        'res_model': 'sale.order',
                                        'channel_record_id': str(order_data['id'])}])
        mock_create_order.assert_called_once()
        
    @ignore_delay
    @no_commit
    @patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder._check_imported_status')
    @patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder._sync_in_queue_job')
    def test_create_log_import_order_missing_product(self, mock_create_order, mock_check_status):
        sale_order_model = self.env['sale.order']
        store = self.test_data['store_2']
        mock_check_status.return_value = True
        order_data = self.test_data['order_data_2']
        sale_order_model.create_jobs_for_synching([order_data], store.id)
        log = self.env['omni.log'].search([('channel_record_id', '=', order_data['id'])])
        self.assertRecordValues(log, [{'datas': order_data, 
                                        'status': 'failed',
                                        'channel_id': store.id,
                                        'operation_type': 'import_order',
                                        'entity_name': order_data['channel_order_ref'],
                                        'res_model': 'sale.order',
                                        'channel_record_id': str(order_data['id'])}])
        
    @ignore_delay
    @no_commit
    @patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder._import_shipments')
    def test_create_log_import_shipment(self, mock_import_shipment):
        sale_order_model = self.env['sale.order']
        store = self.test_data['store_2']
        order = sale_order_model.create({
            'channel_id': store.id,
            'partner_id': self.test_data['main_contact_us_1'].id
        })
        shipments, error_message = [{'id_on_channel': '123123232312'}], None
        mock_import_shipment.return_value = (shipments, error_message)
        order.import_shipments()
        log = self.env['omni.log'].search([('channel_record_id', '=', shipments[0]['id_on_channel']),
                                           ('operation_type', '=', 'import_shipment')])
        
        self.assertRecordValues(log, [{'datas': shipments[0], 
                                        'parent_res_id': order.id,
                                        'parent_res_model': order._name,
                                        'channel_id': order.channel_id.id,
                                        'operation_type': 'import_shipment',
                                        'res_model': 'stock.picking',
                                        'channel_record_id': shipments[0]['id_on_channel'],
                                        'status': 'done',
                                        'message': error_message}])
