odoo.define('omni_base.custom_many2many_checkboxes', function (require) {
    "use strict";

    var FieldMany2ManyCheckBoxes = require('web.relational_fields').FieldMany2ManyCheckBoxes;
    var registry = require('web.field_registry');
    var core = require('web.core');
    var qweb = core.qweb;

    var CustomFieldMany2ManyCheckBoxes = FieldMany2ManyCheckBoxes.extend({
        template: 'CustomFieldMany2ManyCheckBoxes',
        events: _.extend({}, FieldMany2ManyCheckBoxes.prototype.events, {
            'change .select_all': '_selectAll',
        }),
        _renderEdit: function(){
            this.m2mValues = this.record.specialData[this.name];
            this.$el.empty();
            this.$el.html(qweb.render("CustomFieldMany2ManyCheckBoxes", {widget: this}))
        },
        _render: function(){
            var self = this;
            this._super.apply(this, arguments);
            _.each(this.value.res_ids, function (id) {
                self.$('input[data-record-id="' + id + '"]').prop('checked', true);
            });
            if (this.value.res_ids.length == 0){
                _.each(this.m2mValues, function (value) {
                    self.$('input[data-record-id="' + value[0] + '"]').prop('checked', false);
                });
            }

            var ids = _.map(this.$('input:checked'), function (input) {
                return $(input).data("record-id");
            });
            var index = ids.indexOf(undefined);
            if (index > -1) {
              ids.splice(index, 1);
            }
            if (ids.length != this.m2mValues.length){
                this.$(".select_all").prop('checked', false);
            }else{
                this.$(".select_all").prop('checked', true);
            }
        },
        _selectAll: function(ev){
            if ($(ev.currentTarget).is(':checked')){
                _.each(this.m2mValues, function (value) {
                    self.$('input[data-record-id="' + value[0] + '"]').prop('checked', true);
                });
            }else{
                _.each(this.m2mValues, function (value) {
                    self.$('input[data-record-id="' + value[0] + '"]').prop('checked', false);
                });
            }
            this._onChange()
        },
        _onChange: function () {
            var self = this;
            var ids = _.map(this.$('input:checked'), function (input) {
                return $(input).data("record-id");
            });
            var index = ids.indexOf(undefined);
            if (index > -1) {
              ids.splice(index, 1);
            }
            if (ids.length != this.m2mValues.length){
                this.$(".select_all").prop('checked', false);
            }else{
                this.$(".select_all").prop('checked', true);
            }

            if (ids.length == 0){
                this._setValue({
                    operation: 'DELETE_ALL',
                });
            }else{
                this._setValue({
                    operation: 'MULTI',
                    commands: [{
                        operation: 'DELETE_ALL'
                    }, {
                        operation: 'ADD_M2M',
                        ids: _.map(ids, (id) => {
                            let value = self.m2mValues.find(item => item[0] === id);
                            return {
                                id: id,
                                display_name: value ? value[1] : '',
                            }
                        }),
                    }]
                });
            }

        },
    })
    registry.add('custom_many2many_checkboxes', CustomFieldMany2ManyCheckBoxes)
})