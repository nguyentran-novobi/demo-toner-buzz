odoo.define('omni_base.custom_groupby_many2many_checkboxes', function (require) {
    "use strict";

    var FieldMany2ManyCheckBoxes = require('web.relational_fields').FieldMany2ManyCheckBoxes;
    var registry = require('web.field_registry');
    var core = require('web.core');
    var qweb = core.qweb;

    var CustomGroupByMany2ManyCheckBoxes = FieldMany2ManyCheckBoxes.extend({
        template: 'CustomGroupByMany2ManyCheckBoxes',
        events: _.extend({}, FieldMany2ManyCheckBoxes.prototype.events, {
            'change .select_all': '_selectAll',
        }),
        init: function () {
            this._super.apply(this, arguments);
            let values = _.filter(this.m2mValues, function(v){ return v.length == 3});
            if (values != undefined && values.length > 1) {
                this.groupValues = _.groupBy(values, function (v) {
                    return v[2];
                });
                this.groups = _.map(this.groupValues, function(value, key){
                    return key
                });
            }
        },
        _renderEdit: function(){
            this.m2mValues = this.record.specialData[this.name];
            this.$el.empty();
            this.$el.html(qweb.render("CustomGroupByMany2ManyCheckBoxes", {widget: this}))
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

            let values = _.filter(this.m2mValues, function(v){ return v.length == 3});

            if (values != undefined && values.length > 1) {
                let group_by = _.groupBy(values, function (v) {
                    return v[2];
                });
                _.each(group_by, function(value, key){
                    let m2mValues = group_by[key];
                    let ids = _.map(self.$el.find("input[data-group-name='"+key+"']:checked"), function (input) {
                        return $(input).data("record-id");
                    });
                    let input = _.find(self.$el.find(".select_all"), function(e){
                        return $(e).data('group-name') == key;
                    });
                    if (ids.length != m2mValues.length){
                        $(input).prop('checked', false);
                    }else{
                        $(input).prop('checked', true);
                    }
                })
            }
        },
        _selectAll: function(ev){
            let groupName = $(ev.currentTarget).data('group-name');
            let $inputs = this.$el.find("input[data-group-name='"+groupName+"']");
            if ($(ev.currentTarget).is(':checked')){
                _.each($inputs, function (input) {
                    $(input).prop('checked', true);
                });
            }else{
                _.each($inputs, function (input) {
                    $(input).prop('checked', false);
                });
            }
            this._onChange()
        },
        _onChange: function () {
            var ids = _.map(this.$el.find('input.record-id:checked'), function (input) {
                return $(input).data("record-id");
            });
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
                        ids: _.map(ids, function(id){ return {id: id}})
                    }]
                });
            }

        },
    })
    registry.add('custom_groupby_many2many_checkboxes', CustomGroupByMany2ManyCheckBoxes)
})