odoo.define('omni_base.SelectionGroup', function (require) {
    "use strict";

    var FieldSelection = require('web.relational_fields').FieldSelection;
    var registry = require('web.field_registry');

    var SelectionGroupWidget = FieldSelection.extend({
        className: 'o_selection_group',
        template: 'SelectionGroup',
        supportedFieldTypes: ['selection', 'many2one'],
        fieldsToFetch: {
            display_name: {type: 'char'},
        },
        /**
         * @override
         * @returns {boolean} always true
         */
        init: function (parent, params) {
            this._super.apply(this, arguments);
            this.renderedValue = false;
            this.currentValues = this.values;
        },
        willStart: function () {
            var self = this;
            this.allRecords = [];
            if (this.field.type === 'many2one' && this.mode == 'edit') {
                if (this.values.length == 2) {
                    var def = this._rpc({
                        model: this.field.relation,
                        method: 'name_search',
                        kwargs: {
                            name: '',
                            args: [],
                            operator: "!=",
                        },
                    }).then(function (res) {
                        self.values = res;
                        self.allRecords = res;
                    });
                    return Promise.all([def, this._super.apply(this, arguments)]);
                } else {
                    return this._super.apply(this, arguments)
                }
            }else{
                return this._super.apply(this, arguments)
            }
        },
        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * @private
         * @override
         */
        _renderEdit: function () {
            var self = this;
            var currentValue;
            if (this.field.type === 'many2one') {
                currentValue = this.value && this.value.data.id;
            } else {
                currentValue = this.value;
            }
            if (this.values.length == 2) {
                this.values = this.allRecords;
            }
            if (!this.renderedValue | JSON.stringify(this.currentValues)!=JSON.stringify(this.values)){
                this.renderedValue = true;
                this.currentValues = this.values;
                this.$el.empty();
                this.$el.append($('<option/>'));
                if (this.values.length >= 1){
                    let values = _.filter(this.values, function(v){ return v && v.length == 3});
                    if (values != undefined && values.length > 1){
                        let group_by = _.groupBy(values, function(v){ return v[2]; });
                        _.each(group_by, function(value, key){
                            let lines = group_by[key];
                            let $optgroup = $('<optgroup/>');
                            $optgroup.attr("label", key);
                            _.each(lines, function (e) {
                                $optgroup.append($('<option/>', {
                                    value: e[0],
                                    text: e[1],
                                }));
                            });
                            self.$el.append($optgroup)
                        })
                    }else{
                        values = _.filter(this.values, function(v){ return v && v[0]});
                        _.each(values, function (e) {
                            self.$el.append($('<option/>', {
                                value: e[0],
                                text: e[1],
                            }));
                        })
                    }
                }
            }

            if (currentValue){
                this.$el.val(JSON.stringify(currentValue));
            }
        },
    });

    registry.add('selection_group', SelectionGroupWidget);
});
