{
    'name': 'E-commerce Connectors',
    'version': '15.1.0',
    'summary': '',
    'author': 'Novobi LLC',
    'category': 'E-commerce Connectors/E-commerce Connectors',
    'depends': [
        'product', 'sale', 'stock', 'queue_job', 'sale_stock', 
        'sale_management', 'omni_base',
        'web_widget_name_image_url',
    ],
    'data': [
        'security/listing_channel_security.xml',
        'security/ir.model.access.csv',
        'data/queue_job_config_data.xml',
        'data/config_data.xml',
        'views/omnichannel_dashboard_views.xml',
        'views/ecommerce_channel_views.xml',
        'views/customer_channel_views.xml',
        'views/res_partner_views.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'assets': {
        'web.assets_backend': [
            'omni_manage_channel/static/src/scss/ecommerce_channel.scss',
            'omni_manage_channel/static/src/js/list_group_expand.js',
            'omni_manage_channel/static/src/js/action_onboarding.js',
            'omni_manage_channel/static/src/js/action_import_product_channel.js',
            'omni_manage_channel/static/src/js/channel_autocomplete_many2one.js',
        ],
        'web.assets_qweb': [
            'omni_manage_channel/static/src/xml/base.xml',
            'omni_manage_channel/static/src/xml/templates.xml',
        ],
    },
    'license': 'OPL-1'
}

