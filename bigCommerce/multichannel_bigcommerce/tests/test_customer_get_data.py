# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import json
from unittest.mock import patch, MagicMock, Mock
from odoo.addons.channel_base_sdk.utils.bigcommerce_api.resources.customer import DataInTrans
from odoo.addons.omni_manage_channel.tests.utils import get_data_path
from odoo.addons.multichannel_bigcommerce.tests.common import BigCommerceTestCommon, tagged


@tagged('post_install', 'basic_test', '-at_install')
class TestBigCommerceCustomerGetData(BigCommerceTestCommon):

    def test_get_some(self):
        customer_channel_model = self.env['customer.channel']

        bigcommerce_channel = self.bigcommerce_channel_1
            
        with open(get_data_path(__file__, 'data/bigcommerce_get_customers.json'), 'r') as fp:
            res_customer_json = json.load(fp)
            in_transform = DataInTrans()
            transformed_customer_datas = []
            for customer in res_customer_json:
                transformed_customer_datas.append(in_transform(customer))
                    
        with patch('odoo.addons.omni_manage_channel.models.ecommerce_channel.EcommerceChannel.disconnect', autospec=True) as mock_disconnect:
            with patch('odoo.addons.multichannel_bigcommerce.utils.bigcommerce_customer_helper.BigCommerceCustomerImporter.do_import', autospec=True) as mock_do_import:
                with patch('odoo.addons.omni_manage_channel.models.customer_channel.CustomerChannel.create_jobs_for_synching', autospec=True) \
                    as mock_create_jobs_for_synching:
                    mock_do_import.return_value = [Mock(data=transformed_customer_datas)]  
                    customer_channel_model.bigcommerce_get_data(bigcommerce_channel.id)
                    mock_disconnect.assert_not_called()
                    mock_create_jobs_for_synching.assert_called()        
