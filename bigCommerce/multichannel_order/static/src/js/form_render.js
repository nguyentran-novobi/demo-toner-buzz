odoo.define('multichannel_order.FormRenderer', function (require) {
    "use strict";

    var FormRenderer = require('web.FormRenderer');
    FormRenderer.include({
        _renderHeaderButton: function (node) {
            try {
                if (this.state.model == 'sale.order' && this.state.data) {
                    if (this.state.data.is_from_channel) {
                        this.trigger_up('hideEditMode');
                    } else if (this.__parentedParent.is_action_enabled('edit')) {
                        this.trigger_up('showEditMode');
                    }
                }
            }
            catch(error){

            }
            return this._super.apply(this, arguments);
        },
    })
})