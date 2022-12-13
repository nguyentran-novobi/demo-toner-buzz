# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import itertools
import functools
import operator
import json
import re

from unittest.mock import Mock, patch

from odoo import models
from odoo.tests.common import tagged, TransactionCase

from odoo.addons.channel_base_sdk.utils.restful.connection import RestfulRequest


class RequestPatcher:
    TEST_PREFIX = 'test_'
    DEFAULT_PATTERN = {
        'mtd': None,    # 'GET', 'POST', ...
        'url': None,    # a regex to match
        'jsn': {},      # json data to respond
        'hdr': {},      # headers to respond
        'sts': 200,     # status code, e.g.: 200, 404
        'rfs': False,   # exception will be raised for status
        'exc': None,    # exception when sending
    }
    # class shared attributes
    _active_request_patchers = []
    _active_patchers = []

    def __init__(self, *patterns, **kwargs):
        self._initiate_patterns(*patterns, **kwargs)
        self._initiate_patchers()

    def _initiate_patterns(self, *patterns, **kwargs):
        self.patterns = patterns
        extra_pattern = {k: v for k, v in kwargs.items() if k in self.DEFAULT_PATTERN}
        if extra_pattern:
            self.patterns += (extra_pattern,)

    def _initiate_patchers(self):
        self.mock = Mock(name=type(self).__name__)
        self.patchers = [
            patch.object(RestfulRequest, '_send_request', self.request),
            patch.object(RestfulRequest, 'logger'),
        ]

    def __call__(self, func):
        if isinstance(func, type):
            return self._patch_class(func)
        return self._patch_function(func)

    def _patch_class(self, cls):
        for attr in dir(cls):
            if attr.startswith(self.TEST_PREFIX) and callable(attr_value := getattr(cls, attr)):
                patch_attr = self.copy()
                setattr(cls, attr, patch_attr(attr_value))
        return cls

    def _patch_function(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wrapper

    def __enter__(self):
        return self.start()

    def start(self):
        all_arp = self._active_request_patchers
        if not all_arp:
            list(map(operator.methodcaller('start'), self.patchers))
            self._active_patchers.extend(self.patchers)
        all_arp.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def stop(self):
        all_arp = self._active_request_patchers
        all_arp.remove(self)
        if not all_arp:
            list(map(operator.methodcaller('stop'), reversed(self._active_patchers)))

    def __getattr__(self, item):
        return getattr(self.mock, item)

    @property
    def active_patterns(self):
        get_patterns = operator.attrgetter('patterns')
        all_arp = self._active_request_patchers
        return list(itertools.chain(*map(get_patterns, all_arp)))

    @classmethod
    def stop_all(cls):
        all_arp = cls._active_request_patchers.copy()
        list(map(operator.methodcaller('stop'), reversed(all_arp)))

    def copy(self):
        other = type(self)(*self.patterns)
        return other

    def request(self, method, url, *args, **kwargs):
        self._acknowledge(method, url, *args, **kwargs)
        pattern = self._find_first_matched_pattern(method, url)
        return self._build_response_from_pattern(pattern)

    def _acknowledge(self, method, url, *args, **kwargs):
        self.mock(method, url, *args, **kwargs)

    def _find_first_matched_pattern(self, method, url):
        is_match = functools.partial(self._is_pattern_matched, method=method, url=url)
        return next(filter(is_match, self.active_patterns), self.DEFAULT_PATTERN)

    @classmethod
    def _is_pattern_matched(cls, pattern, method, url):
        return (not pattern.get('mtd') or pattern['mtd'].lower() == method.lower()) \
            and (not pattern.get('url') or re.match(pattern['url'], url))

    @classmethod
    def _build_response_from_pattern(cls, pattern):
        if not pattern.get('exc'):
            data_json = pattern.get('jsn', cls.DEFAULT_PATTERN['jsn'])
            data_str = json.dumps(data_json)
            res = Mock(
                content=data_str.encode(),
                text=data_str,
                json=Mock(return_value=data_json),
                headers=pattern.get('hdr', cls.DEFAULT_PATTERN['hdr']),
                status_code=pattern.get('sts', cls.DEFAULT_PATTERN['sts']),
            )
            if pattern.get('rfs'):
                res.raise_for_status = Mock(side_effect=RestfulRequest.engine_response_error)
        else:
            res = Mock(side_effect=pattern['exc'])
        return res


patch_request = RequestPatcher


def patch_model(model, *args, **kwargs):
    def decorate(func):
        @functools.wraps(func)
        def wrapper(obj, *call_args, **call_kwargs):
            with patch.object(type(obj.env[model]), *args, **kwargs) as m:
                return func(obj, *call_args, m, **call_kwargs)

        return wrapper
    return decorate


@tagged('post_install', 'basic_test', '-at_install')
class ListingTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Share data contains data for creating testing data which is used across multiple classes
        cls.shared_data = dict()
        # Test data contains master testing data for testing, of course!
        # It should contains only data can be reused. Transaction data should not be included here.
        # These data is not immutable and may change during the tests.
        # But significant changes are not allowed
        cls.test_data = dict()

        cls._set_up_settings()
        cls._add_users()
        cls._add_companies()
        cls._add_warehouses()
        cls._add_channels()

    def setUp(self):
        super().setUp()
        self.set_up_environment()

    @classmethod
    def _set_up_settings(cls):
        icp_sudo = cls.env['ir.config_parameter'].sudo()
        icp_sudo.set_param('product.weight_in_lbs', '0')  # kg
        icp_sudo.set_param('product.volume_in_cubic_feet', '0')  # m

        cls.env.ref('product.decimal_stock_weight').digits = 7

    @classmethod
    def _add_users(cls):
        """
        Prepare testing users:
        - Admin
        - Listing Manager
        - Listing User
        """
        res_users_model = cls.env['res.users']

        # Admin
        admin_user = res_users_model.create({
            'name': 'Boss!',
            'login': 'boss',
            'password': 'boss',
            'groups_id': [
                (5, 0, 0),
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref('sales_team.group_sale_manager').id),
                (4, cls.env.ref('account.group_account_manager').id),
                (4, cls.env.ref('stock.group_stock_manager').id),
                (4, cls.env.ref('base.group_erp_manager').id),
                (4, cls.env.ref('base.group_system').id),
                (4, cls.env.ref('omni_manage_channel.group_listing_manager').id),
            ],
        })
        admin_user.partner_id.email = 'boss@test.com'

        # Listing Manager
        listing_manager = res_users_model.create({
            'name': 'Listing Manager',
            'login': 'listing_boss',
            'password': 'listing_boss',
            'groups_id': [
                (5, 0, 0),
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref('sales_team.group_sale_manager').id),
                (4, cls.env.ref('account.group_account_manager').id),
                (4, cls.env.ref('stock.group_stock_manager').id),
                (4, cls.env.ref('omni_manage_channel.group_listing_manager').id),
            ],
        })
        listing_manager.partner_id.email = 'listing.boss@test.com'

        # Listing User
        listing_user = res_users_model.create({
            'name': 'Listing User',
            'login': 'listing_minion',
            'password': 'listing_minion',
            'groups_id': [
                (5, 0, 0),
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref('sales_team.group_sale_manager').id),
                (4, cls.env.ref('account.group_account_manager').id),
                (4, cls.env.ref('stock.group_stock_manager').id),
                (4, cls.env.ref('omni_manage_channel.group_listing_user').id),
            ],
        })
        listing_manager.partner_id.email = 'listing.minion@test.com'

        cls.test_data.update({
            'admin_user': admin_user,
            'listing_manager': listing_manager,
            'listing_user': listing_user,
        })

    @classmethod
    def _add_companies(cls):
        res_company_model = cls.env['res.company']

        company_1 = res_company_model.create({
            'name': 'Test Company 1',
            'phone': '+1 512-897-3977',
            'email': 'testing1.company@auto-test.test',
            'street': '1447 Brentwood Drive',
            'street2': 'Suite 555',
            'city': 'Austin',
            'state_id': cls.env.ref('base.state_us_44').id,  # Texas
            'country_id': cls.env.ref('base.us').id,  # USA
            'zip': '78701',
            'website': 'https://testing1-company.auto-test.test',
            'currency_id': cls.env.ref('base.USD').id,
        })

        cls.test_data.update({
            'base_company': cls.env.company,
            'company_1': company_1,
        })

    @classmethod
    def _add_warehouses(cls):
        stock_warehouse_model = cls.env['stock.warehouse']
        warehouses = stock_warehouse_model.search([
            ('company_id', 'in', [cls.test_data['base_company'].id, cls.test_data['company_1'].id])
        ], order='id asc')

        cls.test_data.update({
            'base_warehouse': warehouses.filtered(lambda r: r.company_id == cls.test_data['base_company']),
            'company_1_warehouse_1': warehouses.filtered(lambda r: r.company_id == cls.test_data['company_1']),
        })

    @classmethod
    def _add_channels(cls):
        """
        This method is for preparing ecommerce channels.
        Because channels are defined in separated modules, is is best for those module
        to actual prepare the testing channels.
        """
        pass

    def _set_up_environment(self, user: models.Model, company: models.Model):
        # Shadow the current environment/cursor with the specified user.
        self.env = self.env(user=user)
        self.cr = self.env.cr
        user.company_ids |= company
        user.company_id = company

    def set_up_environment(self):
        """
        This method is meant to be inherited and overwritten.
        Here derived class can set up environment like user and company before running tests.
        """
