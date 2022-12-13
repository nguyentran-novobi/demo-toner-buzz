# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..resource import AmazonResourceModel
from ..registry import register_model
from ..request_builder import AmazonList, AmazonGet, AmazonPost
from .. import resource_formatter as amazon_formatter
class SingularDataInTrans(amazon_formatter.DataTrans):
    """
    Transform only 1 single data of Amazon report from channel to app
    """

    def __call__(self, report):
        return {
            'id': report.get('reportId'),
            'status': report.get('processingStatus', 'IN_QUEUE'),
            'report_document_id': report.get('reportDocumentId'),
            'report_type': report.get('reportType')
        }
        
class DataInTrans(amazon_formatter.DataInTrans):
    """
    Specific data transformer for Amazon report from channel to app
    """
    transform_singular = SingularDataInTrans()
    
@register_model('reports')
class AmazonReportModel(
    AmazonResourceModel,
    AmazonGet,
    AmazonPost,
    AmazonList,
):
    
    """
    An interface of Amazon Report
    """

    path = 'reports/2021-06-30/reports'
    primary_key = 'id'
    transform_in_data = DataInTrans()
    