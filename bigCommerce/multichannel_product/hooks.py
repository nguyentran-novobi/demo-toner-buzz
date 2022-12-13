from odoo import _
from odoo.api import Environment, SUPERUSER_ID
from odoo.exceptions import ValidationError


def pre_init_hook(cr):
    env = Environment(cr, SUPERUSER_ID, {})
    group_data = env['product.product'].read_group([('default_code', 'not in', (False, ''))], ['id', 'default_code'], ['default_code'])
    first = next(filter(lambda g: g['default_code_count'] > 1, group_data), None)
    if first is not None:
        duplicate = first['default_code']
        raise ValidationError(_('Product Internal Reference must be unique. "%s" is not unique.', duplicate))
