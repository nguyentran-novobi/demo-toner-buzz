odoo.define('multichannel_product.ListRenderer', function (require) {
    "use strict";

    var ListRenderer = require('web.ListRenderer');

    ListRenderer.include({
        _renderHeaderCell: function (node) {
            var $th = this._super(node);
            if (node.attrs.widget == 'image_url') {
                $th.css({ textAlign: 'center' });
            }
            else{
                var name = node.attrs.name;
                var field = this.state.fields[name];
                if (field && field.type == "boolean"){
                    $th.css({ textAlign: 'center' });
                }
            }
            return $th
        },
        _onRowClicked: function (ev) {
            let self = this;
            if (this.state.context && this.state.context.dynamic_form_view){
                if (!ev.currentTarget.closest('.o_list_record_selector') && !$(ev.currentTarget).prop('special_click')) {
                    var id = $(ev.currentTarget).data('id');
                    if (id) {
                        let record = this.getParent().model.get(id, {raw: true});
                        this._rpc({
                            model: record.model,
                            method: 'get_dynamic_form_view',
                            args: [[record.res_id]],
                        }).then(function (action) {
                            self.do_action(action)
                        });
                    }
                }
            }else{
                this._super.apply(this, arguments);
            }
        }
    })
})