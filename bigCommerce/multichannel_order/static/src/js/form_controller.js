odoo.define('multichannel_order.FormController', function (require) {
    "use strict";
    var FormController = require('web.FormController');
    FormController.include({
        custom_events: _.extend({}, FormController.prototype.custom_events, {
            hideEditMode: '_onHideEditMode',
            showEditMode: '_onShowEditMode',
        }),
        _onHideEditMode: function(){
            if (this.$buttons) {
                // this.$buttons.find('.o_form_button_edit').hide();
                // this.$buttons.find('.o_form_button_create').addClass('btn-primary').removeClass('btn-secondary');
                this.hide_delete_duplicate = true
            }
        },
        _onShowEditMode: function(){
            if (this.$buttons) {
                // this.$buttons.find('.o_form_button_edit').show();
                // this.$buttons.find('.o_form_button_create').addClass('btn-secondary').removeClass('btn-primary');
                this.hide_delete_duplicate = false
            }
        },
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            if (this.renderer.state.model == 'sale.order' && this.renderer.state.data){
                if (this.renderer.state.data.is_from_channel){
                    this.renderer.trigger_up('hideEditMode');
                }else if (this.renderer.__parentedParent.is_action_enabled('edit')){
                    this.renderer.trigger_up('showEditMode');
                }
            }
        }
    })
})


odoo.define('multichannel_order.Sidebar', function (require) {
    "use strict";

    var Sidebar = require('web.Sidebar');
    Sidebar.include({
        _redraw: function () {
            this._super.apply(this, arguments);
            if (this.__parentedParent.hide_delete_duplicate == true) {
                _.each(this.$el.find('a'), function(a){
                    if ($(a).text().trim() == 'Delete'){
                        $(a).css('display', 'none');
                    }
                    else if ($(a).text().trim() == 'Duplicate'){
                        $(a).css('display', 'none');
                    }
                })
            }else if (this.__parentedParent.hide_delete_duplicate == false){
                _.each(this.$el.find('a'), function(a){
                    if ($(a).text().trim() == 'Delete'){
                        $(a).css('display', 'block');
                    }
                    else if ($(a).text().trim() == 'Duplicate'){
                        $(a).css('display', 'block');
                    }
                })
            }
        },
    })


})