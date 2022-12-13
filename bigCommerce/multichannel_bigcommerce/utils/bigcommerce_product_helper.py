# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
import pytz
import operator
import collections

from datetime import datetime, time
from typing import Any

from .bigcommerce_api_helper import BigCommerceHelper

_logger = logging.getLogger(__name__)


BIGCOMMERCE_REQUEST_SPECIAL_FIELDS = 'variants,images,bulk_pricing_rules,custom_fields'


class ProductExportError(Exception):
    pass


class ProductMapping2ChannelMapper:
    def __init__(self, mapping_template, update=False):
        self.record = mapping_template
        self.update = update

    @classmethod
    def map(cls, mapping_template, update=False):
        return cls(mapping_template, update).do_map()

    def do_map(self):
        data = {
            **self._get_basic_information(),
            **self._get_fulfillment_data(),
            **self._get_product_identifier(),
            **self._get_pricing_and_tax(),
            **self._get_storefront_data(),
            **self._get_seo_and_sharing_data(),
        }
        return data

    def _get_basic_information(self):
        record = self.record
        if record.brand_id:
            brand_id = int(record.brand_id.get_brand_channel(record.channel_id.id).id_on_channel)
        else:
            brand_id = 0
        res = {
            'name': record.name,
            'type': record.type,
            'brand_id': brand_id,
            'sku': record.default_code or '',
            'is_visible': bool(record.is_visible),
            'categories': [int(c.id_on_channel) for c in record.categ_ids],
            'description': record.description_sale or '',
        }
        # Set sku when user want to clear sku on template
        if not res['sku'] and not self.update:
            del res['sku']
        return res

    def _get_fulfillment_data(self):
        record = self.record
        if record.preorder_release_date:
            preorder_release_date = datetime.combine(record.preorder_release_date, time.min).replace(tzinfo=pytz.utc)
            preorder_release_date = preorder_release_date.isoformat()
        else:
            preorder_release_date = None
        return {
            'weight': record.weight_display or 0.0,
            'width': record.width_display or 0.0,
            'depth': record.depth_display or 0.0,
            'height': record.height_display or 0.0,
            'fixed_cost_shipping_price': record.fixed_cost_shipping_price,
            'is_free_shipping': bool(record.is_free_shipping),
            'availability': record.availability,
            'preorder_release_date': preorder_release_date,
            'preorder_message': record.preorder_message or '',
            'is_preorder_only': record.preorder_auto_disable,
            'order_quantity_minimum': int(record.min_order_qty) if record.min_order_qty else 0,
            'order_quantity_maximum': int(record.max_order_qty) if record.max_order_qty else 0,
        }

    def _get_product_identifier(self):
        record = self.record
        res = {
            'upc': record.upc or '',
            'mpn': record.mpn or '',
            'gtin': record.gtin or '',
            'bin_picking_number': record.bin_picking_number or '',
        }
        # Clear UPC and GTIN because UPC and GTIN should be numeric data
        if res['upc'] == '':
            del res['upc']
        if res['gtin'] == '':
            del res['gtin']
        return res

    def _get_pricing_and_tax(self):
        record = self.record
        inventory_tracking = 'none'
        if record.inventory_tracking:
            if record.attribute_line_ids:
                inventory_tracking = 'variant'
            else:
                inventory_tracking = 'product'
        return {
            'price': record.lst_price or 0.0,
            'sale_price': record.sale_price or 0.0,
            'retail_price': record.retail_price or 0.0,
            'tax_class_id': int(record.tax_class_id.id_on_channel),
            'product_tax_code': record.tax_code or '',
            'inventory_tracking': inventory_tracking,
            'inventory_warning_level': int(record.warning_quantity),
            'bulk_pricing_rules': self._get_pricing_rule_data(),
        }

    def _get_pricing_rule_data(self):
        def prepare_pricing_rule_data(rule_line):
            res = {
                'quantity_min': rule_line.quantity_min,
                'quantity_max': rule_line.quantity_max,
                'type': rule_line.discount_type,
                'amount': rule_line.discount_amount,
            }
            if rule_line.id_on_channel:
                res['id'] = rule_line.id_on_channel
            return res
        return list(map(prepare_pricing_rule_data, self.record.bulk_pricing_rule_ids))

    def _get_storefront_data(self):
        record = self.record
        if record.is_related_product_auto:
            related_products = [-1]
        else:
            related_products = list(map(int, record.related_product_ids.mapped('id_on_channel')))
        return {
            'is_featured': bool(record.is_featured),
            'search_keywords': record.search_keywords or '',
            'availability_description': record.availability_description or '',
            'warranty': record.warranty or '',
            'sort_order': record.sort_order or 0,
            'condition': record.bigcommerce_product_condition or '',
            'is_condition_shown': record.bigcommerce_is_product_condition_shown,
            'custom_fields': self._get_custom_field_data(),
            'related_products': related_products,
        }

    def _get_custom_field_data(self):
        def prepare_custom_field_data(custom_line):
            res = {
                'name': custom_line.key,
                'value': custom_line.value,
            }
            if custom_line.id_on_channel:
                res['id'] = custom_line.id_on_channel
            return res

        return list(map(prepare_custom_field_data, self.record.custom_field_ids))

    def _get_seo_and_sharing_data(self):
        record = self.record
        return {
            'page_title': record.page_title or '',
            'meta_description': record.meta_description or '',
            'custom_url': {
                'url': record.slug or record.url or None,
                'is_customized': bool(record.slug),
            },
            'open_graph_type': record.open_graph_type,
            'open_graph_title': record.open_graph_title or '',
            'open_graph_description': record.open_graph_description or '',
            'open_graph_use_meta_description': record.open_graph_use_meta_description,
            'open_graph_use_product_name': record.open_graph_use_product_name,
            'open_graph_use_image': record.open_graph_use_image_option == 'yes',
        }


class ProductAttributeMapping2ChannelExporter:

    option_rep = 'variant_options'
    option_value_rep = 'variant_option_values'

    def __init__(self, mapping_template, attributes):
        self.mapping_template = mapping_template
        self.mapping_template_ioc = mapping_template.id_on_channel
        self.attribute_lines = mapping_template.attribute_line_ids
        self.attributes = attributes
        self.current_remote_options = set(attributes.keys())

        self.api = BigCommerceHelper.connect_with_channel(channel=mapping_template.channel_id)
        self.bulk_actions = {
            self.option_rep: collections.defaultdict(list),
            self.option_value_rep: collections.defaultdict(list),
        }

    @classmethod
    def export(cls, mapping_template, attributes):
        return cls(mapping_template, attributes).do_export()

    def do_export(self):
        self._build_bulk_actions()
        self._do_export()
        return self.bulk_actions

    def _build_bulk_actions(self):
        self._build_bulk_actions_option_delete()
        self._build_bulk_actions_option_create()
        self._build_bulk_actions_option_update()
        self._build_bulk_actions_option_value_delete()

    def _build_bulk_actions_option_delete(self):
        cur_local_options = set(self.attribute_lines.mapped('attribute_id').mapped('name'))

        removed_options = self.current_remote_options - cur_local_options
        self.bulk_actions[self.option_rep]['delete'] = [
            {
                'keys': dict(key=self.attributes[option]['id'], product_id=self.mapping_template_ioc),
            }
            for option in removed_options
        ]

    def _build_bulk_actions_option_create(self):
        added_attribute_lines = self.attribute_lines.filtered(
            lambda ln: ln.attribute_id.name not in self.current_remote_options)
        self.bulk_actions[self.option_rep]['create'] = [
            {
                'keys': dict(key=None, product_id=self.mapping_template_ioc),
                'data': {
                    'product_id': int(self.mapping_template_ioc),
                    'name': attribute_line.attribute_id.name,
                    'display_name': attribute_line.attribute_id.name,
                    'type': 'rectangles',
                    'option_values': [{'label': value.name} for value in attribute_line.value_ids],
                },
            }
            for attribute_line in added_attribute_lines
        ]

    def _build_bulk_actions_option_update(self):
        attributes = self.attributes
        for option_name, cur_local_values, cur_remote_values in self._traverse_local_option_on_remote():
            new_values = cur_local_values - cur_remote_values
            if new_values:
                self.bulk_actions[self.option_rep]['update'].append({
                    'keys': dict(key=attributes[option_name]['id'], product_id=self.mapping_template_ioc),
                    'data': {
                        'id': attributes[option_name]['id'],
                        'option_values': [{'label': value} for value in new_values]
                    },
                })

    def _traverse_local_option_on_remote(self):
        for line in self.attribute_lines:
            option_name = line.attribute_id.name
            if option_name in self.current_remote_options:
                cur_local_values = set(line.value_ids.mapped('name'))
                cur_remote_values = set(self.attributes[option_name].keys()) - {'id'}
                yield option_name, cur_local_values, cur_remote_values

    def _build_bulk_actions_option_value_delete(self):
        attributes = self.attributes
        for option_name, cur_local_values, cur_remote_values in self._traverse_local_option_on_remote():
            removed_option_values = cur_remote_values - cur_local_values
            self.bulk_actions[self.option_value_rep]['delete'].extend(
                {
                    'keys': dict(
                        key=attributes[option_name][value],
                        product_id=self.mapping_template_ioc,
                        option_id=attributes[option_name]['id'],
                    )
                }
                for value in removed_option_values
            )

    def _do_export(self):
        operation_map = {
            'create': 'publish',
            'update': 'put_one',
            'delete': 'delete_one',
        }
        for resource_model, operation_type, resource_values in self.traverse_bulk_actions(self.bulk_actions):
            resource_keys = resource_values['keys']
            resource_data = resource_values.get('data')
            resource = self.api[resource_model].acknowledge(**resource_keys)
            if resource_data:
                resource.data = resource_data
            method = getattr(resource, operation_map[operation_type])
            resource_values['res'] = method()

    @classmethod
    def traverse_bulk_actions(cls, bulk_actions):
        for resource_model, operations in bulk_actions.items():
            for operation_type, resource_value_lists in operations.items():
                for resource_values in resource_value_lists:
                    yield resource_model, operation_type, resource_values


class ProductMapping2ChannelExporter:
    SPECIAL_FIELDS = 'variants,options,bulk_pricing_rules,custom_fields'

    variant_option_exporter = ProductAttributeMapping2ChannelExporter

    def __init__(self, mapping_template, exported_fields=None, update=False):
        assert update, 'Creation export is not supported yet!'
        self.record = mapping_template
        self.record_ioc = mapping_template.id_on_channel
        self.all_variant_records = mapping_template.product_variant_ids
        self.variant_records = self.all_variant_records.filtered(lambda r: r.attribute_value_ids)
        self.channel = mapping_template.channel_id
        self.update = update
        self.exported_fields = exported_fields or {}
        self.exported_template_fields = self.exported_fields.get('template') or {}
        self.exported_variant_fields = self.exported_fields.get('variant') or {}
        self.api = BigCommerceHelper.connect_with_channel(channel=self.channel)

        self.request_data = None
        self.response = None
        self.response_data = None
        self.remote_before_has_options = False
        self.variant_option_responses = None
        self.log_data = None

    @classmethod
    def export(cls, mapping_template, exported_fields=None, update=False):
        return cls(mapping_template, exported_fields, update).do_export()

    def do_export(self):
        self._validate_record()
        self._fetch_current_product_info()
        if not self.response.ok():
            return self
        self._export_dependencies()
        self._export_mapping_variant_options()
        self._export_mapping_template()
        if self.response.ok():
            self._export_other_related_data()
            self._export_mapping_variants()
        self._save_post_export_data()
        self._generate_log_data()
        return self

    def _validate_record(self):
        self.record.ensure_one()

    def _export_dependencies(self):
        self.record._bigcommerce_export_other_data()

    def _fetch_current_product_info(self):
        product = self.api.products.acknowledge(self.record_ioc)
        res = product.get_by_id(include=self.SPECIAL_FIELDS)
        self._store_response(res)

    def _store_response(self, response):
        self.request_data = response.last_response.request.json
        self.response = response
        if response.ok():
            self.response_data = response.data
            self.remote_before_has_options = bool(self.response_data['options'])
        else:
            self.record._bigcommerce_write_errors(response.last_response)
            self.log_data = self.record._bigcommerce_prepare_data(self.update, self.exported_fields)

    def _export_mapping_variant_options(self):
        attributes = self._build_attribute_data_from_stored_response()
        self.variant_option_responses = self.variant_option_exporter.export(self.record, attributes)

    def _build_attribute_data_from_stored_response(self):
        option_data = self.response_data['options']
        return {
            k: v
            for attribute in (
                self._build_attribute_data_from_an_option(option_datum)
                for option_datum in option_data
            )
            for k, v in attribute.items()
        }

    @classmethod
    def _build_attribute_data_from_an_option(cls, option_datum):
        return {
            option_datum['display_name']: {
                'id': option_datum['id'],
                **{
                    option_value['label']: option_value['id']
                    for option_value in option_datum['option_values']
                }
            }
        }

    def _export_mapping_template(self):
        """
        This method exports:
        - Mapping Template
        - Bulk Pricing Rules (New and Updated only)
        - Custom Fields (New and Updated only)
        - Mapping Variants (Updated only)
        """
        product = self.api.products.acknowledge(self.record_ioc)
        data = self.record._bigcommerce_prepare_data(update=self.update, exported_fields=self.exported_fields)
        data = self._adjust_mapping_template_data(data)
        product.data = data
        res = product.put_one(include=self.SPECIAL_FIELDS)
        self._store_response(res)

    def _adjust_mapping_template_data(self, data):
        if self.update:
            variant_ids_on_channel = {str(datum['id']) for datum in self.response_data['variants']}
            data['variants'] = [
                variant._bigcommerce_prepare_data(update=self.update, exported_fields=self.exported_variant_fields)
                for variant in self.variant_records.filtered(lambda r: r.id_on_channel in variant_ids_on_channel)
            ]
        return data

    def _export_other_related_data(self):
        if 'custom_fields' in self.exported_template_fields:
            self._delete_custom_fields()
        if 'bulk_pricing_rules' in self.exported_template_fields:
            self._delete_bulk_pricing_rules()

    def _delete_custom_fields(self):
        product_data = self.response_data
        ex_custom_keys = self.record.custom_field_ids.mapped(operator.itemgetter('key'))
        temp_custom_fields = product_data.get('custom_fields', [])
        outdated_custom_fields = filter(lambda cf: cf['name'] not in ex_custom_keys, temp_custom_fields)

        for cus_field in outdated_custom_fields:
            ack_cus_field = self.api.product_custom_fields.acknowledge(
                cus_field['id'], product_id=self.record_ioc)
            ack_cus_field.delete_one()

    def _delete_bulk_pricing_rules(self):
        product_data = self.response_data
        get_rule_key = operator.itemgetter('quantity_min', 'quantity_max')
        ex_rule_keys = self.record.bulk_pricing_rule_ids.mapped(get_rule_key)
        temp_rules = product_data.get('bulk_pricing_rules', [])
        outdated_rules = list(filter(lambda cf: get_rule_key(cf) not in ex_rule_keys, temp_rules))

        for rule in outdated_rules:
            ack_rule = self.api.product_bulk_pricing_rules.acknowledge(
                rule['id'], product_id=self.record_ioc)
            ack_rule.delete_one()

    def _export_mapping_variants(self):
        """
        Existing variants are already updated during the template update
        Delete variants on Channel when can't find variant_id mapped to variant data in Odoo
        Replace by a new one when don't have it on Channel

        Special cases:
        - If the template has no variants, exporting options has already updated the base variant.
          So there is no need for another variant update
        - If the remote product does not have variants, there is only the base variant.
          So there is no need to delete it
        """
        if not self.record.attribute_line_ids:
            return

        remote_variant_ids_on_channel = {str(datum['id']) for datum in self.response_data['variants']}
        local_variants = self.all_variant_records

        if self.remote_before_has_options:
            local_variant_ids_on_channel = set(local_variants.mapped('id_on_channel'))
            removed_variant_ids_on_channel = remote_variant_ids_on_channel - local_variant_ids_on_channel
            for variant_ioc in removed_variant_ids_on_channel:
                variant = self.api.product_variants.acknowledge(variant_ioc, product_id=self.record_ioc)
                variant.delete_one()

        attributes = self._build_attribute_data_from_stored_response_and_option_responses()
        for variant in local_variants.filtered(lambda r: r.id_on_channel not in remote_variant_ids_on_channel):
            response = variant.bigcommerce_post_record(
                attributes=attributes,
                exported_fields=self.exported_fields['variant']
            )
            if not response.ok():
                self.record._bigcommerce_write_errors(response)

    def _build_attribute_data_from_stored_response_and_option_responses(self):
        def get_options(tvs):
            for resource_model, operation_type, resource_values in tvs:
                if resource_model == 'variant_options' and operation_type != 'delete':
                    res = resource_values['res']
                    if res and res.ok():
                        yield res.data['data']

        traversal = self.variant_option_exporter.traverse_bulk_actions(self.variant_option_responses)
        attributes = self._build_attribute_data_from_stored_response()
        attributes.update({
            k: v
            for attribute in (
                self._build_attribute_data_from_an_option(option_datum)
                for option_datum in get_options(traversal)
            )
            for k, v in attribute.items()
        })
        return attributes

    def _save_post_export_data(self):
        if self.response.ok():
            try:
                custom_field_vals = self._generate_update_custom_field_values()
                bulk_pricing_rule_vals = self._generate_update_bulk_pricing_rule_values()
                self.record.with_context(update_status=True).sudo().write({
                    'state': 'published',
                    'custom_field_ids': custom_field_vals,
                    'bulk_pricing_rule_ids': bulk_pricing_rule_vals,
                    'has_change_image': False,
                })
            except Exception as e:
                _logger.exception(str(e))
                self.record.with_context(update_status=True).sudo().write({
                    'state': 'error',
                    'error_message': str(e),
                })
        else:
            self.record._bigcommerce_write_errors(self.response.last_response)

    def _generate_update_custom_field_values(self):
        product_data = self.response_data
        ex_custom_keys = self.record.custom_field_ids.mapped(operator.itemgetter('key'))
        temp_custom_fields = product_data.get('custom_fields', [])
        ex_custom_data = dict(self.record.custom_field_ids.mapped(operator.itemgetter('key', 'id')))
        intact_custom_fields = filter(lambda cf: cf['name'] in ex_custom_keys, temp_custom_fields)

        return [
            (1, ex_custom_data[cus_field['name']], {'id_on_channel': str(cus_field['id'])})
            for cus_field in intact_custom_fields
        ]

    def _generate_update_bulk_pricing_rule_values(self):
        product_data = self.response_data
        get_rule_key = operator.itemgetter('quantity_min', 'quantity_max')
        ex_rule_keys = self.record.bulk_pricing_rule_ids.mapped(get_rule_key)
        ex_rule_data = dict(self.record.bulk_pricing_rule_ids.mapped(lambda r: (get_rule_key(r), r['id'])))
        temp_rules = product_data.get('bulk_pricing_rules', [])
        intact_rules = list(filter(lambda cf: get_rule_key(cf) in ex_rule_keys, temp_rules))

        return [
            (1, ex_rule_data[get_rule_key(rule)], {'id_on_channel': str(rule['id'])})
            for rule in intact_rules
        ]

    def _generate_log_data(self):
        data = self.request_data
        attributes = self._build_attribute_data_from_stored_response_and_option_responses()
        data.update({
            'options': {
                line.attribute_id.name: line.value_ids.mapped('name')
                for line in self.record.attribute_line_ids
            },
            'variants': [
                variant._bigcommerce_prepare_data(
                    update=True,
                    attributes=attributes,
                    exported_fields=self.exported_variant_fields,
                )
                for variant in self.variant_records
            ],
        })
        self.log_data = data


class ProductImporter:
    channel: Any
    id_on_channel: str = None
    ids_csv: str = None
    limit: int = 250
    from_date: datetime = None
    to_date: datetime = None
    is_visible = False
    all_records = False

    def set_options(self, **options):
        aliases = {
            'date_modified': 'from_date',
        }
        for k, v in options.items():
            att = aliases.get(k, k)
            setattr(self, att, v)

    def do_import(self):
        params = self.prepare_common_params()
        yield from self.get_data(params)

    @classmethod
    def prepare_common_params(cls):
        res = dict(include=BIGCOMMERCE_REQUEST_SPECIAL_FIELDS)
        return res

    def get_data(self, kw):
        try:
            res = self.get_first_data(kw)
            yield res
            yield from self.get_next_data(res)
        except Exception as ex:
            _logger.exception("Error while getting all products: %s", str(ex))
            raise

    def get_first_data(self, kw):
        api = BigCommerceHelper.connect_with_channel(self.channel)
        if self.id_on_channel:
            ack = api.products.acknowledge(self.id_on_channel)
            res = ack.get_by_id(**kw)
        else:
            adj_kw = {**kw, **{
                'include': BIGCOMMERCE_REQUEST_SPECIAL_FIELDS,
                'limit': str(self.limit),
                'sort': 'date_last_imported',
                'direction': 'desc',
                'id:in': self.ids_csv if self.ids_csv else None,
                'date_modified:min': self._format_datetime(self.from_date) if self.from_date else None,
                'date_modified:max': self._format_datetime(self.to_date) if self.to_date else None,
                'is_visible': 'true' if self.is_visible else None,
            }}
            adj_kw = {k: v for k, v in adj_kw.items() if v is not None}
            res = api.products.all(**adj_kw)
        return res

    @classmethod
    def _format_datetime(cls, value):
        return value.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    @classmethod
    def get_next_data(cls, res):
        while res:
            res = res.get_next_page()
            yield res


class ProductImportBuilder:
    products: Any

    def prepare(self):
        if isinstance(self.products, dict):
            self.products = [self.products]
        for product in self.products:
            attributes = self.extract_attributes(product)
            attribute_values = yield attributes
            prod = self.transform_product(product)
            prod['attribute_line_ids'] = attribute_values
            yield prod

    @classmethod
    def extract_attributes(cls, product_data):
        def traverse_options(variants):
            for var in variants:
                for opt_value in var.get('option_values', []):
                    yield opt_value['option_display_name'], opt_value['label']

        attributes = collections.defaultdict(set)
        for option_name, option_value in traverse_options(product_data.get('variants', [])):
            attributes[option_name].add(option_value)
        attributes = {k: list(v) for k, v in attributes.items()}
        return attributes

    @classmethod
    def transform_product(cls, product):
        variants = cls.extract_product_variants(product)
        product['variants'] = variants
        product['inventory_quantity'] = product.get('inventory_level', 0)
        product['url'] = product.get('custom_url') and product['custom_url'].get('url') or ''
        product['product_tmpl_type'] = cls.extract_product_type(product)
        return product

    @classmethod
    def extract_product_variants(cls, product):
        variants = product.get('variants', [])
        variants = [{**v, **{
            'inventory_quantity': float(v.get('inventory_level', 0))
        }} for v in variants]
        return variants

    @classmethod
    def extract_product_type(cls, product):
        if product.get('type') == 'physical':
            if product['inventory_tracking'] != 'none':
                res = 'product'
            else:
                res = 'consu'
        else:
            res = 'service'
        return res
