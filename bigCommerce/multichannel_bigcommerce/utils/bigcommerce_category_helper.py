# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from typing import Any

from .bigcommerce_api_helper import BigCommerceHelper, RateLimit, ExportError, NotFoundError
from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter
from odoo.addons.channel_base_sdk.utils.common.exceptions import EmptyDataError
from odoo.addons.omni_manage_channel.utils.common import ImageUtils


_logger = logging.getLogger(__name__)


class BigcommerceCategoryHelper:
    _api: BigCommerceHelper

    def __init__(self, channel):
        self._api = BigCommerceHelper.connect_with_channel(channel)

    @classmethod
    def prepare_data(cls, category):
        vals = {
            'name': category.name,
            'url': category.url or '',
            'parent_id': int(category.parent_id.id_on_channel or 0),
            'description': category.description or '',
            'sort_order': category.sort_order or 0,
            'default_product_sort': category.bc_default_product_sort,
            'image_url': category.image_url if category.image else '',
            'page_title': category.page_title or '',
            'meta_keywords': [e.strip() for e in category.meta_keywords.split(',')] if category.meta_keywords else [],
            'search_keywords': category.search_keywords or '',
            'meta_description': category.meta_description or '',
            'is_visible': category.is_visible
        }
        return vals

    def create(self, category):
        data = self.prepare_data(category)
        ack = self._api.categories.acknowledge(None)
        ack.data = data
        res = ack.publish()
        if res.ok():
            return res
        elif res.get_status_code() == 429:
            raise RateLimit("Rate limit while exporting categories to Bigcommerce")
        else:
            raise ExportError(res.get_error_message())

    def update(self, category):
        data = self.prepare_data(category)
        ack = self._api.categories.acknowledge(category.id_on_channel)
        ack.data = data
        res = ack.put_one()
        if res.ok():
            return res
        elif res.get_status_code() == 429:
            raise RateLimit("Rate limit while exporting categories to Bigcommerce")
        elif res.get_status_code() == 404:
            raise NotFoundError("Not Found")
        else:
            raise ExportError(res.get_error_message())


class BigCommerceCategoryImporter:
    channel: Any
    ids: list
    all_records = False

    def do_detail_import(self):
        params = self.prepare_common_params()
        yield from self.get_details_data(params)

    def do_tree_import(self):
        params = self.prepare_common_params()
        return self.get_tree_data(params)

    def prepare_common_params(self):
        res = dict(limit='100')
        return res

    def get_tree_data(self, kw):
        try:
            api = BigCommerceHelper.connect_with_channel(self.channel)
            if self.ids:
                vals = []
                for id in self.ids:
                    ack = api.category_tree.acknowledge(id.strip())
                    try:
                        vals.append(ack.get_by_id().data)
                    except EmptyDataError:
                        pass
                res = api.category_tree.create_collection_with(vals)
            else:
                res = api.category_tree.all(**kw)
            return res
        except Exception as ex:
            _logger.exception("Error while getting category: %s", str(ex))
            raise

    def get_details_data(self, kw):
        try:
            res = self.get_first_data(kw)
            yield res
            yield from self.get_next_data(res)
        except Exception as ex:
            _logger.exception("Error while getting category: %s", str(ex))
            raise

    def get_first_data(self, kw):
        api = BigCommerceHelper.connect_with_channel(self.channel)
        if self.ids:
            vals = []
            for id in self.ids:
                ack = api.categories.acknowledge(id.strip())
                try:
                    vals.append(ack.get_by_id().data)
                except EmptyDataError:
                    pass
            res = api.categories.create_collection_with(vals)
        else:
            res = api.categories.all(**kw)
        return res

    def get_next_data(self, res):
        try:
            while res.data:
                res = res.get_next_page()
                yield res
        except EmptyDataError:
            pass


class SingularCategoryDetailDataInTrans(common_formatter.DataTrans):
    def __call__(self, category):
        basic_data = self.process_basic_data(category)
        image_data = self.process_image(category['image_url'])
        result = {
            **basic_data,
            **{'image': image_data}
        }
        return result

    @classmethod
    def process_image(cls, url):
        try:
            image = ImageUtils.get_safe_image_b64(url) if url else False
        except Exception as e:
            _logger.exception("Something went wrong when get image from order item url!")
            image = False
        return image

    @classmethod
    def process_basic_data(cls, category):
        return {
            'id_on_channel': str(category['id']),
            'name': category['name'],
            'url': category['url'],
            'description': category['description'],
            'sort_order': category['sort_order'],
            'bc_default_product_sort': category['default_product_sort'],
            'page_title': category['page_title'],
            'meta_keywords': category['meta_keywords'],
            'search_keywords': category['search_keywords'],
            'meta_description': category['meta_description'],
            'is_visible': category['is_visible'],
        }


class SingularCategoryTreeDataInTrans(common_formatter.DataTrans):
    def __call__(self, channel_id, categories, existing_categories, existed_records, new_options):
        new_results = []
        existing_results = []

        def _extract_tree(list_cat, child_flag=False):
            for p in list_cat:
                child_ids = [(5, 0, 0)]

                # If categories has children
                if p['children']:
                    for c in p['children']:
                        child_cat_dict = _extract_tree([c], child_flag=True)
                        if str(c['id']) in existing_categories:
                            record = existed_records.filtered(lambda r: r.id_on_channel == str(c['id']))
                            if record:
                                record = record[0]
                                child_ids.append((4, record.id))
                        if str(c['id']) in new_options:
                            child_ids.append((0, 0, {
                                'name': c['name'],
                                'channel_id': channel_id,
                                'id_on_channel': str(c['id']),
                                'child_ids': child_cat_dict
                            }))
                # if categories have no parent
                if not child_flag:
                    parent_cat_dict = {}
                    parent_cat_dict['channel_id'] = channel_id
                    parent_cat_dict['name'] = p['name']
                    parent_cat_dict['child_ids'] = child_ids
                    if str(p['id']) in existing_categories:
                        parent_cat_dict['id_on_channel'] = str(p['id'])
                        existing_results.append(parent_cat_dict)
                    if str(p['id']) in new_options:
                        parent_cat_dict['id_on_channel'] = str(p['id'])
                        new_results.append(parent_cat_dict)
                # else categories have parent
                else:
                    return child_ids

        _extract_tree(categories)

        return new_results, existing_results


class BigcommerceCategoryImportBuilder:
    channel_id: Any
    categories: Any
    existing_categories: Any
    existed_records: Any
    new_options: Any
    transform_tree_data = SingularCategoryTreeDataInTrans()
    transform_detail_data = SingularCategoryDetailDataInTrans()

    def prepare_tree(self):
        return self.transform_tree_data(self.channel_id, self.categories, self.existing_categories, self.existed_records, self.new_options)

    def prepare_detail(self):
        for category in self.categories:
            yield self.transform_detail_data(category)
