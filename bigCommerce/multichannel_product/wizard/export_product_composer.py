import itertools
import operator

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ExportProduct(models.TransientModel):
    """
    This wizard is used to select product channel of product template
    """
    _name = 'export.product.composer'
    _description = 'Export Product Composer'

    product_tmpl_id = fields.Many2one('product.template', string='Product Template')
    product_channel_ids = fields.One2many(
        'product.channel',
        'product_tmpl_id',
        related="product_tmpl_id.product_channel_ids",
        string='Products Channel',
    )

    channel_ids = fields.Many2many(
        'ecommerce.channel',
        string='Stores',
        required=True,
        domain=[
            ('platform', '!=', False),
            ('can_export_product_from_master', '=', True),
            ('is_mapping_managed', '=', True),
            ('can_export_product', '=', True),
        ],
    )
    product_product_ids = fields.Many2many('product.product', string='SKUs')
    product_product_count = fields.Integer('Number of master variants', compute='_compute_product_product_count')

    product_preview_ids = fields.One2many('product.export.preview', 'export_product_composer_id', string='SKUs to Export', compute='_compute_product_preview_ids', readonly=True)

    @api.model
    def _process_product_preview_for_each_channel(self, product_variants, channel):
        channel = channel._origin
        product_previews = []
        for variant in product_variants:
            product_alt_skus = variant.product_alternate_sku_ids.filtered(lambda p: p.channel_id == channel)
            if product_alt_skus:
                product_previews.extend(
                    (0, 0, {
                        'default_code': product_alt.name,
                        'sequence': product_alt.sequence,
                        'channel_id': channel.id,
                        'product_id': variant.id,
                        'product_channel_variant_id': product_alt.product_channel_variant_id.id,
                    })
                    for product_alt in product_alt_skus
                )
            else:
                product_mapping_variants = variant.product_channel_variant_ids.filtered(
                    lambda p: p.channel_id == channel)
                if product_mapping_variants:
                    for product_mapping_variant in product_mapping_variants:
                        product_previews.append((0, 0, {
                            'default_code': variant.default_code,
                            'sequence': 0,
                            'channel_id': channel.id,
                            'product_id': variant.id,
                            'product_channel_variant_id': product_mapping_variant.id
                        }))
                else:
                    product_previews.append((0, 0, {
                        'default_code': variant.default_code,
                        'sequence': 0,
                        'channel_id': channel.id,
                        'product_id': variant.id,
                        'product_channel_variant_id': False,
                    }))
        return product_previews

    @api.depends('channel_ids')
    def _compute_product_preview_ids(self):
        for record in self:
            product_tmpls = self._get_selected_product_templates()
            product_variants = product_tmpls.mapped('product_variant_ids')
            product_previews = sum((
                self._process_product_preview_for_each_channel(product_variants, channel)
                for channel in record.channel_ids
            ), [(5, 0, 0)])

            record.update({
                'product_preview_ids': product_previews
            })

    @api.depends('product_tmpl_id')
    def _compute_product_product_count(self):
        for record in self:
            if record.product_tmpl_id:
                record.product_product_count = len(record.product_tmpl_id.product_variant_ids)
            else:
                record.product_product_count = 0

    @api.model
    def _prepare_exported_vals(self, product_tmpl, channel, map_variant):
        def is_variant_match(pcv):
            return pcv.product_product_id in map_variant \
                and pcv.default_code == map_variant[pcv.product_product_id]

        def has_all_variant_match(pc):
            return all(is_variant_match(pcv) for pcv in pc.product_variant_ids)

        product_channels = product_tmpl.product_channel_ids.filtered(lambda p: p.channel_id == channel)
        product_channels = product_channels.filtered(has_all_variant_match)
        is_updated = bool(product_channels)
        vals = product_tmpl.with_context(export_from_master=True)._prepare_product_channel_data(
            channel=channel, update=is_updated, map_variant=map_variant)
        if not is_updated:
            vals.update({
                'product_tmpl_id': product_tmpl.id,
                'channel_id': channel.id,
                'inventory_tracking': False if product_tmpl.type in ['service', 'consu'] else True,
            })
        return product_channels, vals

    def _check_invalid_product(self, channel):
        def either_all_or_none_mapping(records, mapping_getter):
            mapping_variants_it = itertools.tee(map(mapping_getter, records), 2)
            return all(mapping_variants_it[0]) or all(map(operator.not_, mapping_variants_it[1]))

        def same_num_of_alt(variants):
            return len(set(len(self.get_alt_skus(variant, channel)) or 1 for variant in variants)) == 1

        mapping_from_master = operator.attrgetter('product_channel_variant_ids')
        mapping_from_alt = operator.attrgetter('product_channel_variant_id')
        product_tmpls = self._get_selected_product_templates()
        for product_tmpl in product_tmpls:
            product_variants = product_tmpl.product_variant_ids
            alternate_skus = product_tmpl.product_alternate_sku_ids
            if not either_all_or_none_mapping(product_variants, mapping_from_master) \
                    or not either_all_or_none_mapping(alternate_skus, mapping_from_alt) \
                    or not same_num_of_alt(product_variants):
                raise ValidationError(_('Do not support export for this product!'))

            product_previews = self.product_preview_ids.filtered(
                lambda p, tmpl=product_tmpl: p.product_id.product_tmpl_id == tmpl)
            if not all(product_preview.default_code for product_preview in product_previews):
                raise ValidationError(_('SKU is required. Please add Alternate SKU for the selected store.'))

    def _get_selected_product_templates(self):
        self.ensure_one()
        product_ids = list(map(int, self.env.context.get('active_ids', [])))
        return self.product_tmpl_id or self.env['product.template'].browse(product_ids)

    @api.model
    def get_alt_skus(self, variant, channel):
        return variant.product_alternate_sku_ids.filtered(lambda p: p.channel_id == channel)

    @api.model
    def prepare_product_channel_data_for_export_separately(self, product_tmpl, channel):
        alternate_skus = product_tmpl.product_alternate_sku_ids
        channel_alt_sku = alternate_skus\
            .filtered(lambda alt: alt.channel_id == channel)\
            .sorted(lambda alt: (alt.product_product_id.id, alt.sequence, alt.id))

        product_dict = {
            product: channel_alt_sku.browse().concat(*g).mapped('name')
            for product, g in itertools.groupby(channel_alt_sku, key=lambda p: p.product_product_id)
        }

        return product_dict

    def export(self):
        self.ensure_one()
        for channel in self.channel_ids:
            channel.with_context(active_test=False).ensure_operating()

        exported_mappings = self.env['product.channel'].browse()
        product_tmpls = self._get_selected_product_templates()
        channels = self.channel_ids
        delay_exec = any([
            len(channels) > 1,
            len(product_tmpls) > 1,
            min(len(self.get_alt_skus(pv, channels[:1])) or 1 for pv in product_tmpls[:1].product_variant_ids) > 1,
        ])

        for product_tmpl in product_tmpls:
            product_variants = product_tmpl.product_variant_ids
            for channel in self.channel_ids:
                self._check_invalid_product(channel)
                self._add_alt_sku_to_variant_if_not_exists(product_variants, channel)
                product_dict = self.prepare_product_channel_data_for_export_separately(product_tmpl, channel)
                number_of_group = min(len(self.get_alt_skus(pv, channel)) or 1 for pv in product_variants)
                for index in range(number_of_group):
                    map_variant = {k: v[index] for k, v in product_dict.items()}
                    product_channels, vals = self._prepare_exported_vals(product_tmpl, channel, map_variant)
                    product_channel = product_channels[:1]
                    product_channel = self._create_or_update_mapping(product_channel, vals)
                    self._update_alternate_sku_mapping(product_tmpl, product_channel)
                    product_channel.with_context(delay_exec=delay_exec).do_export_from_master_data(channel)
                    exported_mappings |= product_channel

        return self._return_action_after_process(exported_mappings, self.channel_ids)

    @api.model
    def _add_alt_sku_to_variant_if_not_exists(self, variants, channel):
        for variant in variants.filtered(lambda v: not self.get_alt_skus(v, channel)):
            variant.update({
                'product_alternate_sku_ids': [(0, 0, {
                    'name': variant.default_code,
                    'sequence': 0,
                    'channel_id': channel.id,
                    'product_channel_variant_id': False,
                })]
            })

    @api.model
    def _create_or_update_mapping(self, product_channels, vals):
        ctx = dict(export_from_master=True)
        if product_channels:
            product_channels.with_context(**ctx).write(vals)
        else:
            product_channels = product_channels.with_context(**ctx).create(vals)
        return product_channels

    @api.model
    def _update_alternate_sku_mapping(self, product_tmpl, product_channel):
        channel = product_channel.channel_id
        map_product_sku = {
            (variant.product_product_id, variant.default_code): variant
            for variant in product_channel.product_variant_ids
        }
        alternate_skus = product_tmpl.product_alternate_sku_ids
        channel_alt_sku = alternate_skus.filtered(lambda alt: alt.channel_id == channel)
        for alt_sku in channel_alt_sku:
            variant = map_product_sku.get((alt_sku.product_product_id, alt_sku.name))
            if variant:
                alt_sku.product_channel_variant_id = variant

    @api.model
    def _return_action_after_process(self, mappings, channels):
        if len(mappings) == 1 and len(channels) == 1:
            cust_method_name = '%s_get_mapping_views' % channels[0].platform
            form_id = False
            if hasattr(channels[0], cust_method_name):
                parent, view_ids = getattr(channels[0], cust_method_name)()
                form_id = view_ids[2][2]['view_id']

            return {
                'name': 'Create Product On Channel',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'product.channel',
                'view_id': form_id,
                'res_id': mappings[:1].id,
                'type': 'ir.actions.act_window',
                'context': {'form_view_initial_mode': 'edit'}
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Notification!'),
                    'message': _('Products are exporting....'),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

    @api.onchange('channel_id')
    def onchange_channel_id(self):
        """
        Place for other channels to inherit
        """
        return {}


class ProductExportPreview(models.TransientModel):
    _name = 'product.export.preview'
    _description = 'Product Export Preview'
    _rec_name = 'product_id'
    _order = 'sequence, id'

    export_product_composer_id = fields.Many2one('export.product.composer', ondelete='cascade')
    default_code = fields.Char(string='SKU')
    sequence = fields.Integer()
    product_id = fields.Many2one('product.product', string='Product')
    channel_id = fields.Many2one('ecommerce.channel', string='Store')
    product_channel_variant_id = fields.Many2one('product.channel.variant', string='Product Mapping')
