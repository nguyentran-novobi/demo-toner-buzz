{
    'name': 'Novobi: Partner Deposit',
    'summary': 'Novobi: Partner Deposit',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '15.1.0',
    'depends': [
        'l10n_generic_coa',
        'account_reports',
        'account',
        'account_followup'
    ],

    'data': [
        # ============================== DATA =================================
        'data/coa_chart_data.xml',

        # ============================== SECURITY =============================
        'security/ir.model.access.csv',

        # ============================== VIEWS ================================
        'views/res_partner_view.xml',
        'views/account_payment_deposit_view.xml',
        'views/account_move_views.xml',

        # ============================== REPORT ===============================
        'report/account_followup_report_templates.xml',

        # ============================== WIZARDS ==============================
        'wizard/deposit_order_view.xml',

    ],
    'installable': True,
    'auto_install': False,
    'assets': {
        'web.assets_qweb': [
            'account_partner_deposit/static/src/xml/account_payment.xml',
        ],
    },
    'license': 'OPL-1'
}
