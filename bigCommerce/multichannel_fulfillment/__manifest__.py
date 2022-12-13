{
    'name': 'Order Fulfillment',
    'version': '15.1.0',
    'summary': '',
    'author': 'Novobi LLC',
    'category': 'E-commerce Connectors',
    'depends': [
        'omni_manage_channel',
        'multichannel_product',
    ],
    'data': [
        'data/ir_sequence_data.xml',
        'data/config_data.xml',
        'data/queue_job_config_data.xml',
        'data/system_parameters_data.xml',

        'security/ir.model.access.csv',

        'views/omnichannel_dashboard_views.xml',
        'views/ecommerce_channel_views.xml',
        'views/product_channel_views.xml',
        'views/product_channel_variant_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_service_picking_views.xml',
        'views/exclude_inventory_sync_views.xml',
        'views/shipping_method_channel_views.xml',

        'wizard/stock_service_immediate_transfer_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
    'post_init_hook': 'post_init_hook',
}
