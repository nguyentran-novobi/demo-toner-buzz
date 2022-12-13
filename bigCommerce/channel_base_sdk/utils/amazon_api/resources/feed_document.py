# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common.resource import delegated
from ..resource import AmazonResourceModel
from ..registry import register_model
from ..request_builder import AmazonList, AmazonGet, AmazonPost, make_request_builder
from .. import resource_formatter as amazon_formatter

class SingularDataInTrans(amazon_formatter.DataTrans):
    """
    Transform only 1 single data of Amazon report from channel to app
    """

    def __call__(self, feed):
        return {
            'id': feed.get('feedDocumentId'),
            'url': feed.get('url', ''),
        }
        
class DataInTrans(amazon_formatter.DataInTrans):
    """
    Specific data transformer for Amazon report from channel to app
    """
    transform_singular = SingularDataInTrans()
    
@register_model('feed_document')
class AmazonReportModel(
    AmazonResourceModel,
    AmazonGet,
    AmazonPost,
    AmazonList,
):
    
    """
    An interface of Amazon Feed Document
    """

    path = 'feeds/2021-06-30/documents'
    primary_key = 'id'
    transform_in_data = DataInTrans()
    
    