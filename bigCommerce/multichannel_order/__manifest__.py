{
    'name': 'Order Management',
    'version': '15.1.0',
    'summary': '',
    'author': 'Novobi LLC',
    'category': 'E-commerce Connectors',
    'depends': [
        'omni_manage_channel',
        'multichannel_product',
        'multichannel_fulfillment',
        'sale',
        'stock',
        'delivery',
        'sale_partner_deposit'
    ],
    'data': [
        'security/ir.model.access.csv',

        'data/config_data.xml',
        'data/default_data.xml',
        'data/queue_job_config_data.xml',
        'data/mail_template_data.xml',

        'wizard/order_channel_cancel_confirmation.xml',

        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/omnichannel_dashboard_views.xml',
        'views/sale_report_templates.xml',
        'wizard/import_order_operation.xml',
        'views/order_process_rule_views.xml',
        'views/order_status_channel_views.xml',
        'views/customer_groups_views.xml',
        'views/payment_gateway_views.xml',
        'views/payment_method_mapping_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1'
}
