# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from .currency import BigCommerceCurrencyModel
from .customer import BigCommerceCustomerModel
from .product import BigCommerceProductModel
from .variant import BigCommerceProductVariantModel
from .variant_option import BigCommerceVariantOptionModel
from .variant_option_value import BigCommerceVariantOptionValueModel
from .product_image import BigCommerceProductImageModel
from .category import BigCommerceCategoryModel
from .category_tree import BigCommerceCategoryTreeModel
from .brand import BigCommerceBrandModel
from .tax_class import BigCommerceTaxClassModel
from .pricelist import BigCommercePricelistModel
from .pricelist_record import BigCommercePricelistRecordModel
from .pricelist_assignment import BigCommercePricelistAssignmentModel
from .order import BigCommerceOrderModel
from .order_tax import BigCommerceOrderTaxModel
from .order_shipment import BigCommerceOrderShipmentModel
from .order_shipping_address import BigCommerceOrderShippingAddressModel
from .order_products import BigCommerceOrderProductModel
from .order_coupons import BigCommerceOrderCouponModel
from .customer_address import BigCommerceCustomerAddressModel
from .payment_method import BigCommercePaymentMethodModel
from .customer_group import BigCommerceCustomerGroupModel
from .payment_gateway import BigCommercePaymentGatewayModel
from . import other_resources
