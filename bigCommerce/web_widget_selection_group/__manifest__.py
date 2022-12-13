{
    'name': 'Omni: Selection Group Widget',
    'version': '15.1.0',
    'summary': '',
    'author': 'Novobi LLC',
    'depends': [
        'web'
    ],
    'data': [
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'assets': {
        'web.assets_backend': [
            'web_widget_selection_group/static/src/js/selection_group.js',
        ],
        'web.assets_qweb': [
            'web_widget_selection_group/static/src/xml/base.xml',
        ],
    },
    'license': 'OPL-1'
}

