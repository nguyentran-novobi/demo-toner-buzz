{
    'name': 'Product Manage Variant Price',
    'version': '15.1.0',
    'summary': '',
    'author': 'Novobi LLC',
    'category': 'E-commerce Connectors',
    'depends': [
        'multichannel_product',
    ],
    'data': [
        'security/groups.xml',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
    'pre_init_hook': 'pre_init_hook',
}

