# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import operator
import functools
import contextlib
import logging

from typing import Any

from odoo import tools, _

from odoo.addons.channel_base_sdk.utils.common.exceptions import NoResponseError

from .bigcommerce_api_helper import BigCommerceHelper

_logger = logging.getLogger(__name__)


class PricelistMaster2MappingMapper:
    def __init__(self, pricelist, channel):
        self.env = pricelist.env
        self.pricelist = pricelist
        self.channel = channel

    def do_map(self):
        res = {
            **self._map_basic(),
            **self._map_rules(),
            **self._map_misc(),
        }
        return res

    def _map_basic(self):
        return {
            'name': self.pricelist.name,
            'pricelist_id': self.pricelist.id,
            'channel_id': self.channel.id,
            'currency_id': self.pricelist.currency_id.id,
        }

    def _map_rules(self):
        map_item = self._map_rule_items
        adding_rule_vals = sum((map_item(item) for item in self.pricelist.item_ids), [])
        clear_all_vals = [(5, 0, {})]
        return {
            'rule_ids': clear_all_vals + adding_rule_vals,
        }

    def _map_rule_items(self, item) -> list:
        variants = self._get_applied_variants_from(item)
        item_mapper = PricelistItemMaster2MappingMapper
        adding_item_vals = [
            (0, 0, item_mapper(item, variant).do_map())
            for variant in variants
        ]
        return adding_item_vals

    def _get_applied_variants_from(self, item):
        applying_rule = item.applied_on
        if applying_rule == '3_global':
            res = self.env['product.channel.variant'].search([('channel_id', '=', self.channel.id)])
        elif applying_rule == '2_product_category':
            master = self.env['product.product'].search([('categ_id', 'child_of', item.categ_id.id)])
            res = self._get_store_mapping_from_master(master)
        elif applying_rule == '1_product':
            res = self._get_store_mapping_from_master(item.product_tmpl_id.mapped('product_variant_ids'))
        else:  # applying_rule is 0_product_variant
            res = self._get_store_mapping_from_master(item.product_id)
        return res

    def _get_store_mapping_from_master(self, product):
        return product.mapped('product_channel_variant_ids').filtered(lambda r: r.channel_id == self.channel)

    @classmethod
    def _map_misc(cls):
        return {
            'need_to_export': True,
        }


class PricelistItemMaster2MappingMapper:
    DISCOUNT_TYPE_MASTER_TO_MAPPING = {
        'fixed': 'fixed',
        'percentage': 'percent',
        'formula': 'fixed',
    }

    def __init__(self, item, variant):
        self.item = item
        self.variant = variant

    def do_map(self) -> dict:
        """
        Return the vals of `channel.pricelist.rule`
        {
            'product_channel_variant_id': int,
            'is_override_lst_price': True,
            'override_lst_price': float,
        }
        OR
        {
            'product_channel_variant_id': int,
            'bulk_pricing_discount_type': str,
            'bulk_pricing_rule_ids': [
                (0, 0, {
                    'quantity_min': float,
                    'discount_amount_fixed': float,
                })
            ]
        }
        OR
        {
            'product_channel_variant_id': int,
            'bulk_pricing_discount_type': str,
            'bulk_pricing_rule_ids': [
                (0, 0, {
                    'quantity_min': float,
                    'discount_amount_percent': float,
                })
            ]
        }
        """

        res = {
            'product_channel_variant_id': self.variant.id,
        }
        if self.item.min_quantity <= 1.0:
            res.update(self._generate_rule_vals_for_variant_qty_singular())
        else:
            res.update(self._generate_rule_vals_for_variant_qty_plural())
        return res

    def _generate_rule_vals_for_variant_qty_singular(self):
        return {
            'is_override_lst_price': True,
            'override_lst_price': self._compute_price(),
        }

    def _compute_price(self):
        """
        Compute price similarly to `_compute_price` of `product.pricelist.item`
        """

        item = self.item
        compute_type = item.compute_price
        if compute_type == 'fixed':
            res = item.fixed_price
        elif compute_type == 'percentage':
            res = self.variant.lst_price * (1 - item.percent_price / 100.0)
        else:  # compute_type is formula
            res = self._compute_price_formula()
        return res

    def _compute_price_formula(self):
        item = self.item
        price_limit = price = self.variant.lst_price
        price = price * (1 - (item.price_discount / 100)) or 0.0
        if item.price_round:
            price = tools.float_round(price, precision_rounding=item.price_round)

        if item.price_surcharge:
            price_surcharge = item.price_surcharge
            price += price_surcharge

        if item.price_min_margin:
            price_min_margin = item.price_min_margin
            price = max(price, price_limit + price_min_margin)

        if item.price_max_margin:
            price_max_margin = item.price_max_margin
            price = min(price, price_limit + price_max_margin)
        return price

    def _generate_rule_vals_for_variant_qty_plural(self):
        return {
            'bulk_pricing_discount_type': self.DISCOUNT_TYPE_MASTER_TO_MAPPING[self.item.compute_price],
            'bulk_pricing_rule_ids': [
                (0, 0, self._generate_pricing_rule_vals_for_variant_qty_plural())
            ]
        }

    def _generate_pricing_rule_vals_for_variant_qty_plural(self):
        item = self.item
        res = {
            'quantity_min': item.min_quantity,
        }
        if item.compute_price == 'percentage':
            res.update({
                'discount_amount_percent': item.percent_price,
            })
        else:
            res.update({
                'discount_amount_fixed': self._compute_price(),
            })
        return res


class PricelistExporter:
    def __init__(self, pricelist):
        self.pricelist = pricelist
        self.channel = pricelist.channel_id
        self.can_be_retried = False
        self.bigcommerce_api = BigCommerceHelper.connect_with_channel(self.channel)

    @property
    def workflow(self):
        if self.pricelist.is_exported_to_store:
            if self.can_be_retried:
                return 'to_post'
            return 'to_put'
        return 'to_post'

    def do_export(self):
        data = self._prepare_data()
        pricelist_obj = self._export_with(data)
        return pricelist_obj

    def _prepare_data(self):
        return {
            'name': self.pricelist.name,
            'active': self.pricelist.is_published,
        }

    def _export_with(self, data):
        if self.workflow == 'to_put':
            res = self._put_and_monitor(data)
        else:
            res = self._post_with(data)
        return res

    def _put_and_monitor(self, data):
        res = self._put_with(data)
        if res.get_status_code() == 404:
            self.can_be_retried = True
        return res

    def _put_with(self, data):
        ioc = self.pricelist.id_on_channel
        pricelist_obj = self.bigcommerce_api.pricelists.acknowledge(ioc)
        pricelist_obj.data = data
        return pricelist_obj.put_one()

    def _post_with(self, data):
        pricelist_obj = self.bigcommerce_api.pricelists.create_new_with(data)
        return pricelist_obj.publish()


class PricelistRuleExporter:
    MAX_NUMBER_OF_RULES = 1000

    def __init__(self, pricelist):
        self.pricelist = pricelist
        self.channel = pricelist.channel_id
        self.bigcommerce_api = BigCommerceHelper.connect_with_channel(self.channel)

    def do_export(self):
        data = self._prepare_data()
        pricelist_rule_obj = self._export_with(data)
        return pricelist_rule_obj

    def _prepare_data(self):
        return [
            self._prepare_rule_data(rule)
            for rule in self.pricelist.rule_ids
        ]

    @classmethod
    def _prepare_rule_data(cls, rule):
        price_map = {
            'lst_price': 'price',
            'retail_price': 'retail_price',
            'sale_price': 'sale_price',
        }
        res = {
            'variant_id': int(rule.product_channel_variant_id.id_on_channel),
            'currency': rule.currency_id.name,
            'price': rule.catalog_price,
        }
        for price_field, bc_price_field in price_map.items():
            if rule[f'is_override_{price_field}']:
                res[bc_price_field] = rule[f'override_{price_field}']
        if rule.bulk_pricing_rule_ids:
            res['bulk_pricing_tiers'] = [
                {
                    'quantity_min': rule_line.quantity_min,
                    'type': rule_line.discount_type,
                    'amount': rule_line.discount_amount,
                }
                for rule_line in rule.bulk_pricing_rule_ids
            ]
        return res

    def _export_with(self, data):
        ioc = self.pricelist.id_on_channel
        pricelist_obj = self.bigcommerce_api.pricelists.acknowledge(ioc)
        res = pricelist_obj.remove_all_rules()
        if res.last_response.ok():
            for chunk in self.chunks(data, self.MAX_NUMBER_OF_RULES):
                res = pricelist_obj.upsert_records(chunk)
                if not res.last_response.ok():
                    return res
        return res

    @classmethod
    def chunks(cls, lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]


class PricelistAssignmentExporter:
    def __init__(self, pricelist):
        self.pricelist = pricelist
        self.channel = pricelist.channel_id
        self.bigcommerce_api = BigCommerceHelper.connect_with_channel(self.channel)

    def do_export(self):
        data = self._prepare_data()
        pricelist_assignment_obj = self._export_with(data)
        return pricelist_assignment_obj

    def _prepare_data(self):
        return [
            self._prepare_assignment_data(customer_group)
            for customer_group in self.pricelist.channel_customer_group_ids
        ]

    def _prepare_assignment_data(self, customer_group):
        return {
            'price_list_id': int(self.pricelist.id_on_channel),
            'customer_group_id': int(customer_group.id_on_channel),
        }

    def _export_with(self, data):
        delete_query = dict(price_list_id=self.pricelist.id_on_channel)
        res = self.bigcommerce_api.pricelist_assignments.delete_all(**delete_query)
        if res.last_response.ok() and data:
            recognized = self.bigcommerce_api.pricelist_assignments.recognize()
            recognized.data = data
            res = recognized.assign_all()
        return res


class PricelistExportWorkflow:
    class HTTPError(Exception):
        pass

    last_response: Any

    def __init__(self, pricelist):
        self.pricelist = pricelist
        self.error_msgs = []

    @classmethod
    def do_export(cls, pricelist):
        self = cls(pricelist)
        with self._monitor_for_logging():
            self._export_pricelist()
            self._export_pricelist_rules()
            self._export_pricelist_assignments()
            self._acknowledge_exportation_successful()

    @contextlib.contextmanager
    def _monitor_for_logging(self):
        try:
            yield
        except self.HTTPError:
            pass
        finally:
            if self.error_msgs:
                self._log_error_onto_pricelist(self.error_msgs)
            self._acknowledge_process_finished()

    def _log_error_onto_pricelist(self, msgs):
        self.pricelist._log_exceptions('Cannot export pricelist', [
            {
                'title': 'Cannot export pricelist',
                'reason': msg,
            }
            for msg in msgs
        ])

    def _export_pricelist(self):
        helper = PricelistExporter(self.pricelist)
        res = helper.do_export()
        try:
            self._ensure_response_ok(res.last_response)
        except self.HTTPError:
            if helper.can_be_retried:
                self.error_msgs.pop()
                res = helper.do_export()
                self._ensure_response_ok(res.last_response)
                self._log_retry_successfully()
            else:
                raise
        self._save_pricelist({'id_on_channel': res.data['id']})

    def _log_retry_successfully(self):
        self.pricelist.message_post(body=_('A new record is created successfully on online store.'))

    def _save_pricelist(self, vals):
        self.pricelist.with_context(for_synching=True).update(vals)

    def _export_pricelist_rules(self):
        res = PricelistRuleExporter(self.pricelist).do_export()
        self._ensure_response_ok(res.last_response)

    def _export_pricelist_assignments(self):
        res = PricelistAssignmentExporter(self.pricelist).do_export()
        self._ensure_response_ok(res.last_response)

    def _ensure_response_ok(self, last_response):
        self.last_response = last_response
        if not self.last_response.ok():
            self.error_msgs.append(last_response.get_error())
            try:
                last_response.raise_for_status()
            except IOError as ex:
                raise self.HTTPError(str(ex))

    def _acknowledge_exportation_successful(self):
        self._save_pricelist({'need_to_export': False})

    def _acknowledge_process_finished(self):
        self._save_pricelist({'is_sync_in_progress': False})


class PricelistImporter:
    def __init__(self, channel, **kwargs):
        self.channel = channel
        self.options = kwargs
        self.bigcommerce_api = BigCommerceHelper.connect_with_channel(self.channel)

    def do_import(self):
        res = self._get_first_page()
        yield from res
        yield from self._get_next_page(res)

    def _get_first_page(self):
        res = []
        if self.options.get('all_records'):
            res = self.bigcommerce_api.pricelists.all()
        if self.options.get('ids'):
            csv = ','.join(map(str, self.options['ids']))
            res = self.bigcommerce_api.pricelists.all(**{'id:in': csv})
        return res

    @classmethod
    def _get_next_page(cls, pricelist_res):
        while pricelist_res:
            pricelist_res = pricelist_res.get_next_page()
            yield from pricelist_res


class PricelistRuleImporter:
    def __init__(self, channel, pricelist_id):
        self.channel = channel
        self.pricelist_id = pricelist_id
        self.bigcommerce_api = BigCommerceHelper.connect_with_channel(self.channel)

    def do_import(self):
        res = self._get_first_page()
        yield res
        yield from self._get_next_page(res)

    def _get_first_page(self):
        acknowledged = self.bigcommerce_api.pricelist_records.acknowledge(None, pricelist_id=self.pricelist_id)
        return acknowledged.all(include='bulk_pricing_tiers')

    @classmethod
    def _get_next_page(cls, rule_res):
        while rule_res:
            rule_res = rule_res.get_next_page()
            yield rule_res


class PricelistAssignmentImporter:
    def __init__(self, channel, pricelist_ids):
        self.channel = channel
        self.pricelist_ids = pricelist_ids
        self.bigcommerce_api = BigCommerceHelper.connect_with_channel(self.channel)

    def do_import(self):
        res = self._get_first_page()
        yield res
        yield from self._get_next_page(res)

    def _get_first_page(self):
        csv = ','.join(map(str, self.pricelist_ids))
        return self.bigcommerce_api.pricelist_assignments.all(**{'price_list_id:in': csv})

    @classmethod
    def _get_next_page(cls, assignment_res):
        while assignment_res:
            assignment_res = assignment_res.get_next_page()
            yield assignment_res


class PricelistChannel2MappingDelegateMapper:

    def __init__(self, channel, pricelist_res):
        self.channel = channel
        self.pricelist = pricelist_res
        self.rules = []
        self.assignments = []

    def add_rules(self, rules_res):
        self.rules.extend(rules_res)

    def add_assignments(self, assignment_res):
        self.assignments.extend(filter(bool, assignment_res))

    def do_map(self):
        assert len(self.pricelist) == 1
        return self._parse_pricelist_data(self.pricelist.data)

    def _parse_pricelist_data(self, data):
        ioc = data['id']
        parse_assignment_data = functools.partial(self._parse_assignment_data, price_list_id=ioc)
        return {
            'channel_id': self.channel.id,
            'id_on_channel': str(data['id']),
            'name': data['name'],
            'is_published': data['active'],
            'rules': sum(map(self._parse_rule_data, self.rules), []),
            'assignments': sum(map(list, map(parse_assignment_data, self.assignments)), []),
        }

    @classmethod
    def _parse_rule_data(cls, rules_res):
        mapper = PricelistItemChannel2MappingDelegateMapper(rules_res)
        return mapper.do_map()

    @classmethod
    def _parse_assignment_data(cls, assignment_res, price_list_id):
        for res in assignment_res:
            data = res.data
            if data['price_list_id'] == price_list_id:
                yield {
                    'channel_customer_group_id_on_channel': data['customer_group_id'],
                }


class PricelistItemChannel2MappingDelegateMapper:

    def __init__(self, rules_res):
        self.rules = rules_res

    def do_map(self):
        assert len(self.rules) > 0
        get_data = operator.attrgetter('data')
        parse_rule = self._parse_rule_data
        res = list(map(parse_rule, map(get_data, self.rules)))
        return res

    @classmethod
    def _parse_rule_data(cls, data):
        parse_pricing_rule = cls._parse_bulk_pricing_rule_data
        return {
            'price_list_id_on_channel': str(data['price_list_id']),
            'product_channel_variant_id_on_channel': str(data['variant_id']),
            'lst_price': data['price'] or None,
            'sale_price': data['sale_price'] or None,
            'retail_price': data['retail_price'] or None,
            'calculated_price': data['calculated_price'] or None,
            'currency_code': data['currency'].upper(),
            'bulk_pricing_rules': list(map(parse_pricing_rule, data.get('bulk_pricing_tiers', []))),
        }

    @classmethod
    def _parse_bulk_pricing_rule_data(cls, data):
        return {
            'quantity_min': data['quantity_min'],
            'quantity_max': data['quantity_min'],
            'discount_type': data['type'],
            'discount_amount': data['amount'],
        }


class PricelistMappingDelegate2MappingMapper:

    def __init__(self, env, data):
        self.env = env
        self.data = data

    @property
    def channel_id(self) -> int:
        return self.data['channel_id']

    @property
    def ioc(self) -> str:
        return self.data['id_on_channel']

    @tools.lazy_property
    def pricelist(self):
        return self.env['channel.pricelist'].search([
            ('channel_id', '=', self.channel_id),
            ('id_on_channel', '=', self.ioc),
        ], limit=1)

    @tools.lazy_property
    def mapping_variants(self):
        get_ioc = operator.itemgetter('product_channel_variant_id_on_channel')
        variant_ids_on_channel = list(map(get_ioc, self.data['rules']))
        variants = self.env['product.channel.variant'].search([
            ('channel_id', '=', self.channel_id),
            ('id_on_channel', 'in', variant_ids_on_channel),
        ])
        return variants

    @tools.lazy_property
    def mapping_customer_groups(self):
        groups = self.env['channel.customer.group'].search([
            ('channel_id', '=', self.channel_id),
            ('id_on_channel', 'in', self.group_ids_on_channel),
        ])
        return groups

    @property
    def group_ids_on_channel(self):
        get_ioc = operator.itemgetter('channel_customer_group_id_on_channel')
        return list(map(get_ioc, self.data['assignments']))

    @property
    def workflow(self) -> str:
        return 'update' if self.pricelist else 'create'

    def do_map(self):
        res = {
            **self._parse_pricelist_data(),
            **self._parse_rules_data(),
            **self._parse_customer_groups_data(),
        }
        return res

    def _parse_pricelist_data(self):
        data = self.data
        first_rule = next(iter(data['rules']), {})
        currency_code = first_rule.get('currency_code')
        currency = self.env['res.currency'].search([('name', '=like', currency_code)], limit=1)
        res = {
            'name': data['name'],
            'is_published': data['is_published'],
            'currency_id': currency.id,
        }
        if self.workflow == 'create':
            res.update({
                'channel_id': self.channel_id,
                'id_on_channel': self.ioc,
            })
        return res

    def _parse_rules_data(self):
        data = self.data
        clear_vals = [(5, 0, {})]
        item_mapper = PricelistItemMappingDelegate2MappingMapper
        rule_vals = [
            (0, 0, item_mapper(self.env, rule, self.mapping_variants).do_map())
            for rule in data['rules']
        ]
        res = {
            'rule_ids': clear_vals + rule_vals
        }
        return res

    def _parse_customer_groups_data(self):
        self._ensure_customer_group_exists()
        groups = self.mapping_customer_groups
        group_ids = groups.ids
        return {
            'channel_customer_group_ids': [(6, 0, group_ids)],
        }

    def _ensure_customer_group_exists(self):
        existing_ids = set(map(int, self.mapping_customer_groups.mapped('id_on_channel')))
        missing_ids = set(self.group_ids_on_channel) - set(existing_ids)
        if missing_ids:
            first_id = next(iter(missing_ids))
            raise ValueError(f'Unable to find customer group with ID "{first_id}" in the system.')


class PricelistItemMappingDelegate2MappingMapper:

    def __init__(self, env, data, variants):
        self.env = env
        self.data = data
        self.variants = variants

    def do_map(self):
        res = {
            **self._parse_rule_data(),
            **self._parse_rule_lines_data(),
        }
        return res

    def _parse_rule_data(self):
        data = self.data
        variant_ioc = data['product_channel_variant_id_on_channel']
        mapping_variant = self._ensure_variant_exists(variant_ioc)
        res = {
            'product_channel_variant_id': mapping_variant.id,
            'is_override_lst_price': data['lst_price'] is not None,
            'is_override_retail_price': data['retail_price'] is not None,
            'is_override_sale_price': data['sale_price'] is not None,
            'override_lst_price': self._float(data['lst_price']),
            'override_retail_price': self._float(data['retail_price']),
            'override_sale_price': self._float(data['sale_price']),
        }
        return res

    def _ensure_variant_exists(self, variant_ioc):
        mapping_variant = self.variants.filtered(lambda r: r.id_on_channel == variant_ioc)
        if not mapping_variant:
            raise ValueError(f'Unable to find product with ID "{variant_ioc}" in the system.')
        return mapping_variant

    def _parse_rule_lines_data(self):
        data = self.data
        first_rule_line = next(iter(data['bulk_pricing_rules']), {})
        if first_rule_line:
            return {
                'bulk_pricing_discount_type': first_rule_line['discount_type'],
                'bulk_pricing_rule_ids': [
                    (0, 0, self._parse_rule_line_data(rule_line))
                    for rule_line in data['bulk_pricing_rules']
                ]
            }
        return {}

    @classmethod
    def _parse_rule_line_data(cls, line):
        res = {
            'quantity_min': line['quantity_min'],
            'discount_amount': line['discount_amount'],
        }
        return res

    @classmethod
    def _float(cls, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


class PricelistImportLogger:
    options: dict
    env: Any

    @property
    def data_operation(self):
        return 'all' if self.options.get('all_records') else 'by_ids'

    def log(self, **kwargs):
        vals = {
            'datas': dict(),
            'channel_id': False,
            'operation_type': 'import_others',
            'data_type_id': self.env.ref('multichannel_bigcommerce.channel_pricelist_data_type').id,
            'data_operation': self.data_operation,
            'res_id': False,
            'res_model': 'channel.pricelist',
            'status': 'done',
            'message': '',
            'channel_record_id': '',
        }
        vals.update(kwargs)
        return self.env['omni.log'].create(vals)


class PricelistImportWorkflow(PricelistImportLogger):
    class HTTPError(Exception):
        pass

    pricelists: dict
    assignments: list
    last_response: Any

    def __init__(self, channel, **kwargs):
        self.channel = channel
        self.env = channel.env
        self.options = kwargs
        self.delegate_values = []

    @property
    def data_ids(self):
        ids = self.options.get('ids') or []
        return ','.join(map(str, ids))

    def log(self, **kwargs):
        logging_vals = {
            'datas': dict(data=self.delegate_values),
            'channel_id': self.channel.id,
            'channel_record_id': self.data_ids,
        }
        logging_vals.update(kwargs)
        super().log(**logging_vals)

    @classmethod
    def import_to_delegate(cls, channel, **kwargs):
        self = cls(channel, **kwargs)
        with self._monitor_for_logging():
            for delegate_vals in self._import_to_delegate():
                self.delegate_values.append(delegate_vals)
                yield delegate_vals

    @contextlib.contextmanager
    def _monitor_for_logging(self):
        try:
            yield
        except self.HTTPError as ex:
            last_error_msg = self.last_response.get_error() if self.last_response else ''
            self.log(status='failed', message=f'{ex}\n{last_error_msg}')
        except Exception as ex:
            _logger.warning('Logged: %s', str(ex), exc_info=True)
            self.log(status='failed', message=f'{ex}')

    def _import_to_delegate(self):
        pricelists = self._import_matched_pricelists()
        if pricelists:
            assignments = self._import_matched_pricelist_assignments()
            for pricelist_ioc, pricelist_res in pricelists.items():
                mapper = PricelistChannel2MappingDelegateMapper(self.channel, pricelist_res)
                mapper.add_assignments(assignments)
                for rules_res in self._import_pricelist_rules(pricelist_ioc):
                    mapper.add_rules(rules_res)
                yield mapper.do_map()

    def _import_matched_pricelists(self):
        self.pricelists = dict(self._import_pricelists())
        return self.pricelists

    def _import_pricelists(self):
        pricelist_importer = PricelistImporter(self.channel, **self.options)
        for pricelist_res in pricelist_importer.do_import():
            self._ensure_response_ok(pricelist_res.last_response)
            yield pricelist_res.key, pricelist_res

    def _ensure_response_ok(self, last_response):
        self.last_response = last_response
        try:
            last_response.raise_for_status()
        except IOError as ex:
            raise self.HTTPError(str(ex)) from ex
        except NoResponseError:
            pass

    def _import_matched_pricelist_assignments(self):
        self.assignments = list(self._import_pricelist_assignments())
        return self.assignments

    def _import_pricelist_assignments(self):
        assignment_importer = PricelistAssignmentImporter(self.channel, list(self.pricelists.keys()))
        for assignment_res in assignment_importer.do_import():
            self._ensure_response_ok(assignment_res.last_response)
            yield assignment_res

    def _import_pricelist_rules(self, pricelist_ioc):
        rule_importer = PricelistRuleImporter(self.channel, pricelist_ioc)
        for rules_res in rule_importer.do_import():
            self._ensure_response_ok(rules_res.last_response)
            yield rules_res


class PricelistDelegateWorkflow(PricelistImportLogger):
    OVERRIDDEN_VALUES = {
        'need_to_export': False,
        'is_sync_in_progress': False,
    }

    def __init__(self, model, delegate_vals, **kwargs):
        self.model = model
        self.env = model.env
        self.delegate_vals = delegate_vals
        self.options = kwargs
        self.mapper = PricelistMappingDelegate2MappingMapper(model.env, delegate_vals)
        self.pricelist = model.browse()

    @property
    def data_ids(self):
        return self.mapper.ioc

    def log(self, **kwargs):
        logging_vals = {
            'datas': self.delegate_vals,
            'channel_id': self.delegate_vals['channel_id'],
            'channel_record_id': self.data_ids,
        }
        logging_vals.update(kwargs)
        super().log(**logging_vals)

    @classmethod
    def save_delegate(cls, model, delegate_vals, **kwargs):
        self = cls(model, delegate_vals, **kwargs)
        with self._monitor_for_logging():
            vals = self._do_map()
            vals.update(cls.OVERRIDDEN_VALUES)
            with self._savepoint():
                self._save_delegate(vals)
        return self.pricelist

    def _do_map(self):
        return self.mapper.do_map()

    def _savepoint(self):
        return self.env.cr.savepoint()

    def _save_delegate(self, vals):
        if self.mapper.workflow == 'create':
            self.pricelist = self.model.with_context(for_synching=True).create(vals)
        else:
            self.pricelist = self.mapper.pricelist
            self.pricelist.with_context(for_synching=True).update(vals)
        return self.pricelist

    @contextlib.contextmanager
    def _monitor_for_logging(self):
        try:
            yield
        except Exception as ex:
            _logger.warning('Logged: %s', str(ex), exc_info=True)
            self.log(status='failed', message=str(ex))
        else:
            self.log(status='done', message='')
