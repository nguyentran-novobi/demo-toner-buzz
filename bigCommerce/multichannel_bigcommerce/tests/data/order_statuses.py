ORDER_STATUSES = [
  {
    "id": 0,
    "name": "Incomplete",
    "system_label": "Incomplete",
    "custom_label": "Incomplete - Testing",
    "system_description": "An incomplete order happens when a shopper reached the payment page, but did not complete the transaction.",
    "order": 0
  },
  {
    "id": 1,
    "name": "Pending",
    "system_label": "Pending",
    "custom_label": "Pending",
    "system_description": "Customer started the checkout process, but did not complete it.",
    "order": 1
  },
  {
    "id": 2,
    "name": "Shipped",
    "system_label": "Shipped",
    "custom_label": "Shipped",
    "system_description": "Order has been shipped, but receipt has not been confirmed; seller has used the Ship Items action.",
    "order": 8
  },
  {
    "id": 3,
    "name": "Partially Shipped",
    "system_label": "Partially Shipped",
    "custom_label": "Partially Shipped",
    "system_description": "Only some items in the order have been shipped, due to some products being pre-order only or other reasons.",
    "order": 6
  },
  {
    "id": 4,
    "name": "Refunded",
    "system_label": "Refunded",
    "custom_label": "Refunded",
    "system_description": "Seller has used the Refund action.",
    "order": 11
  },
  {
    "id": 5,
    "name": "Cancelled",
    "system_label": "Cancelled",
    "custom_label": "Cancelled",
    "system_description": "Seller has cancelled an order, due to a stock inconsistency or other reasons.",
    "order": 9
  },
  {
    "id": 6,
    "name": "Declined",
    "system_label": "Declined",
    "custom_label": "Declined",
    "system_description": "Seller has marked the order as declined for lack of manual payment, or other reasons.",
    "order": 10
  },
  {
    "id": 7,
    "name": "Awaiting Payment",
    "system_label": "Awaiting Payment",
    "custom_label": "Awaiting Payment",
    "system_description": "Customer has completed checkout process, but payment has yet to be confirmed.",
    "order": 2
  },
  {
    "id": 8,
    "name": "Awaiting Pickup",
    "system_label": "Awaiting Pickup",
    "custom_label": "Awaiting Pickup",
    "system_description": "Order has been pulled, and is awaiting customer pickup from a seller-specified location.",
    "order": 5
  },
  {
    "id": 9,
    "name": "Awaiting Shipment",
    "system_label": "Awaiting Shipment",
    "custom_label": "Awaiting Shipment",
    "system_description": "Order has been pulled and packaged, and is awaiting collection from a shipping provider.",
    "order": 4
  },
  {
    "id": 10,
    "name": "Completed",
    "system_label": "Completed",
    "custom_label": "Completed - Testing",
    "system_description": "Client has paid for their digital product and their file(s) are available for download.",
    "order": 7
  },
  {
    "id": 11,
    "name": "Awaiting Fulfillment",
    "system_label": "Awaiting Fulfillment",
    "custom_label": "Awaiting Fulfillment",
    "system_description": "Customer has completed the checkout process and payment has been confirmed.",
    "order": 3
  },
  {
    "id": 12,
    "name": "Manual Verification Required",
    "system_label": "Manual Verification Required",
    "custom_label": "Manual Verification Required",
    "system_description": "Order on hold while some aspect needs to be manually confirmed.",
    "order": 13
  },
  {
    "id": 13,
    "name": "Disputed",
    "system_label": "Disputed",
    "custom_label": "Disputed",
    "system_description": "Customer has initiated a dispute resolution process for the PayPal transaction that paid for the order.",
    "order": 12
  },
  {
    "id": 14,
    "name": "Partially Refunded",
    "system_label": "Partially Refunded",
    "custom_label": "Partially Refunded",
    "system_description": "Seller has partially refunded the order.",
    "order": 14
  }
]