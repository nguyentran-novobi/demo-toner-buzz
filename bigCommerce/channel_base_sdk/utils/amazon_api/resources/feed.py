# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..resource import AmazonResourceModel
from ..registry import register_model
from ..request_builder import AmazonList, AmazonGet, AmazonPost
from .. import resource_formatter as amazon_formatter


class SingularDataInTrans(amazon_formatter.DataTrans):
    """
    Transform only 1 single data of Amazon feed from channel to app
    """

    def __call__(self, feed):
        return {
            'id': feed.get('feedId'),
            'status': feed.get('processingStatus', 'IN_QUEUE'),
            'feed_document_id': feed.get('resultFeedDocumentId'),
            'feed_type': feed.get('feedType')
        }
        
class DataInTrans(amazon_formatter.DataInTrans):
    """
    Specific data transformer for Amazon feed from channel to app
    """
    transform_singular = SingularDataInTrans()
    
@register_model('feeds')
class AmazonReportModel(
    AmazonResourceModel,
    AmazonGet,
    AmazonPost,
    AmazonList,
):
    
    """
    An interface of Amazon Feed
    """

    path = 'feeds/2021-06-30/feeds'
    primary_key = 'id'
    transform_in_data = DataInTrans()
    