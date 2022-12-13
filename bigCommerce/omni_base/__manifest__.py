{
    'name': 'Omni: Base',
    'version': '15.1.0',
    'summary': '',
    'author': 'Novobi LLC',
    'depends': [
        'web_widget_name_image_url'
    ],
    'data': [
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'assets': {
        'web.assets_backend': [
            'omni_base/static/src/js/custom_many2many_checkboxes.js',
            'omni_base/static/src/js/boolean_button_widget.js',
            'omni_base/static/src/js/kanban_dashboard_graph.js',
            'omni_base/static/src/js/logo_and_name_widget.js',
            'omni_base/static/src/js/list_render.js',
            'omni_base/static/src/js/select_image_widget.js',
            'omni_base/static/src/js/variants_many2many_widget.js',
            'omni_base/static/src/js/custom_groupby_many2many_checkboxes.js',
            'omni_base/static/src/css/style.css',
            'omni_base/static/src/scss/style.scss',
        ],
        'web.assets_qweb': [
            'omni_base/static/src/xml/base.xml',
        ],
    },
    'license': 'OPL-1',
}

