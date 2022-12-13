{
    'name': 'Novobi: Sale Partner Deposit',
    'summary': 'Novobi: Sale Partner Deposit',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '15.1.0',
    'depends': [
        'account_partner_deposit',
        'sale_management'
    ],
    'data': [
        'views/account_payment_deposit_view.xml',
        'views/sale_order_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'OPL-1'
}
