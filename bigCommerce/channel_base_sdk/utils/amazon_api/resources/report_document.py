# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common.resource import delegated
from ..resource import AmazonResourceModel
from ..registry import register_model
from ..request_builder import AmazonGet, AmazonList
from .. import resource_formatter as amazon_formatter

class SingularDataInTrans(amazon_formatter.DataTrans):
    """
    Transform only 1 single data of Amazon report document from channel to app
    """

    def __call__(self, report):
        return {
            'id': report['reportDocumentId'],
            'url': report['url'],
            'compression_algorithm': report['compressionAlgorithm']
        }
        
class DataInTrans(amazon_formatter.DataInTrans):
    """
    Specific data transformer for Amazon report document from channel to app
    """
    transform_singular = SingularDataInTrans()
    
@register_model('report_document')
class AmazonReportDocumentModel(
    AmazonResourceModel,
    AmazonGet,
    AmazonList,
):
    
    """
    An interface of Amazon Report Document
    """

    path = 'reports/2021-06-30/documents'
    primary_key = 'id'
    
    