odoo.define('multichannel_product.FormViewDialog', function (require) {
    "use strict";

    var FormViewDialog = require('web.view_dialogs').FormViewDialog;
    FormViewDialog.include({
        init: function (parent, options) {
            if (options.res_model == 'product.channel.variant'){
                options.disable_multiple_selection = true
            }
            this._super(parent, options);
        }
    })
})