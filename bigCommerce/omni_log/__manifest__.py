{
    'name': 'Log Management',
    'version': '15.1.0',
    'summary': '',
    'author': 'Novobi LLC',
    'category': 'E-commerce Connectors',
    'depends': [
        'queue_job', 'product', 'sale', 'stock', 'multichannel_product', 'multichannel_order'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/config_data.xml',
        'data/cron_job_data.xml',
        'views/base_omni_log_views.xml',
        'views/omni_log_views.xml',
        
    ],
    'installable': True,
    'auto_install': True,
    'application': False,
    'license': 'OPL-1'
}
