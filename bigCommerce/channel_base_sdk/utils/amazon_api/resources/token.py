# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common import PropagatedParam
from ...common.resource import delegated
from ...restful.request_builder import RestfulRequestBuilder, RequestBuilder, make_request_builder

from ..resource import AmazonResourceModel


class OAuthTokenModel(
    RestfulRequestBuilder,
    AmazonResourceModel
):
    """
    Build requests to get tokens from Amazon OAuth server
    """

    primary_key = None

    @delegated
    @make_request_builder(
        method='POST',
        uri='',
    )
    def refresh_token(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None):
        """
        Exchange authorization code for refresh and access tokens
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        """
        prop.data = {**prop.data, **{
            'grant_type': 'refresh_token',
        }}
        return self.build_data_send_handle_json(
            request_builder,
            prop=prop,
        )
