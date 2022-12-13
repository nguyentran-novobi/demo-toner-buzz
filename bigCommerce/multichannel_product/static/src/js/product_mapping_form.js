odoo.define('omniborders.ProductMappingForm', function (require) {
    "use strict";

    const core = require('web.core');
    const viewRegistry = require('web.view_registry');
    const FormView = require('web.FormView');
    const Dialog = require('web.Dialog');
    const FormController = require('web.FormController');
    const _t = core._t;

    const ProductMappingFormController = FormController.extend({
        /**
         * @override
         * overwrite
         */
        _deleteRecords: function (ids) {
            const doIt = () => {
                return this.model
                    .deleteRecords(ids, this.modelName)
                    .then(this._onDeletedRecords.bind(this, ids));
            };
            if (this.confirmOnDelete) {
                const message = _t("Are you sure you want to delete this record? This will not delete the product on the online store.");
                Dialog.confirm(this, message, { confirm_callback: doIt });
            } else {
                doIt();
            }
        },
    });

    const ProductMappingFormView = FormView.extend({
        config: _.extend({}, FormView.prototype.config, {
            Controller: ProductMappingFormController,
        }),
    });

    viewRegistry.add('product_mapping_form', ProductMappingFormView);
});
