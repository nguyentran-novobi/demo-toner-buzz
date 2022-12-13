# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import re
import urllib.parse
from typing import Optional

from ..common import PropagatedParam
from ..common.resource import delegated

from ..restful.request_builder import make_request_builder, RequestBuilder,\
    RestfulRequestBulkBuilder


PAGINATED_LINK = 'paginated_link'


class ShopifyPaginated(RestfulRequestBulkBuilder):
    """
    Manages operations that fetch resources from a list of many pages
    """
    PAGINATED_LINK_REGEX = r'<(?P<link>[^<>]+)>; ?rel="(?P<rel>\w+)"'

    @classmethod
    def pass_result_to_handler(cls, **kwargs):
        response = kwargs.get('response')
        if response and response.ok():
            res_extra_content = {
                PAGINATED_LINK: kwargs['response'].headers.get('Link')
            }
            return super().pass_result_to_handler(**kwargs, extra=res_extra_content)
        return super().pass_result_to_handler(**kwargs)

    @delegated
    @make_request_builder(
        method='GET',
        uri='',
        no_body=True,
    )
    def get_next_from_link(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Get remaining resource from the next link
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        :param kwargs: Optional search criteria
        """
        raw_paginated_link = prop.extra_content[PAGINATED_LINK]
        if raw_paginated_link:
            next_paginated_link = self._extract_paginated_link(raw_paginated_link)
            if next_paginated_link:
                url, params = self.extract_url_and_params(next_paginated_link)
                return self.build_json_send_handle_json(
                    request_builder,
                    prop=prop,
                    url=url,
                    params={**params, **kwargs},
                )
        return self.pass_result_to_handler(nil=True)

    @classmethod
    def extract_url_and_params(cls, link: str):
        parsed = urllib.parse.urlparse(link)
        url = f'{parsed.scheme}://{parsed.hostname}{parsed.path}'
        params = urllib.parse.parse_qs(parsed.query)
        params = dict(
            (k, v[0]) if len(v) == 1 else (f'{k}[]', v)
            for k, v in params.items()
        )
        return url, params

    @classmethod
    def _extract_paginated_link(cls, link: str, rel='next') -> Optional[str]:
        """
        Extract link from response headers with the specified rel
        """
        for paginated_link in link.split(', '):
            match = re.match(cls.PAGINATED_LINK_REGEX, paginated_link)
            if match and match.group('rel') == rel:
                return match.group('link')
        return None
