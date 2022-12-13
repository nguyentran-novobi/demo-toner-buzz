{
    'name': 'BigCommerce Connector',
    'version': '15.1.0',
    'summary': '',
    'author': 'Novobi LLC',
    'category': 'E-commerce Connectors',
    'depends': [
        'multichannel_order', 'omni_log'
    ],
    'data': [
        'security/ir.model.access.csv',

        'data/product_imported_field_data.xml',
        'data/product_exported_field_data.xml',
        'data/bigcommerce_order_status.xml',
        'data/config_data.xml',
        'data/queue_job_config_data.xml',
        'data/menu_data.xml',
        'data/channel_data_type.xml',
        'data/resource_import_operation_type_data.xml',

        'views/ecommerce_channel_views.xml',
        'views/product_channel_views.xml',
        'views/tax_class_views.xml',
        'views/omnichannel_dashboard_views.xml',
        'views/product_channel_category_views.xml',
        'views/channel_pricelist_views.xml',
        'views/customer_groups_views.xml',

        'wizard/import_other_data_composer.xml',
        'wizard/export_pricelist_composer.xml',

        'views/product_pricelist_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'OPL-1'
}
