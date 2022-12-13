from odoo.tools.float_utils import float_compare
from odoo.addons.multichannel_order.utils.order_processing_helper import SingularOrderDataInTrans, OrderProcessingBuilder


class BigCommerceSingleOrderDataInTrans(SingularOrderDataInTrans):

    def __call__(self, order_data, channel_id, default_product_ids):
        header_content = self._process_header_content(channel_id, order_data)
        notes = self._process_notes(order_data)
        warehouse = self._prcess_warehouse(order_data)
        discount_lines = self._process_discount_lines(order_data, default_product_ids)
        fee_lines = self._process_fee_lines(order_data, default_product_ids)
        lines = [(5, 0, 0)] + discount_lines + fee_lines
        result = {
            **header_content,
            **notes,
            **warehouse,
            **{
                'order_line': lines
            }
        }

        return result

    @classmethod
    def _process_fee_lines(cls, order_data, default_product_ids):
        lines = []
        for key in ['shipping', 'handling', 'wrapping', 'other_fees']:
            if float_compare(float(order_data.get('%s_cost' % key, 0)), 0, precision_digits=2) > 0:
                vals = {
                    'product_id': default_product_ids[key],
                    'product_uom_qty': 1,
                    'name': ('%s Cost' % key).replace('_', ' ').title(),
                    'price_unit': order_data.get('%s_cost' % key, 0),
                    'tax_id': [(5, 0, 0)],
                    'tax_amount': order_data.get('%s_cost_tax' % key, 0.0),
                    'is_delivery': True if key == 'shipping' else False,
                    'is_handling': True if key == 'handling' else False,
                    'is_wrapping': True if key == 'wrapping' else False,
                    'is_other_fees': True if key == 'other_fees' else False,
                    'sequence': 5
                }
                lines.append((0, 0, vals))
        if lines:
            lines.append((0, 0, {
                'display_type': 'line_section',
                'name': 'Other Fees',
                'sequence': 4}))
        return lines

class BigCommerceOrderProcessingBuilder(OrderProcessingBuilder):
    transform_data = BigCommerceSingleOrderDataInTrans()