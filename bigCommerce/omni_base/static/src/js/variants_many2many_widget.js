odoo.define('omni_base.variants_many2many_widget', function (require) {
    "use strict";

    var FieldMany2ManyCheckBoxes = require('web.relational_fields').FieldMany2ManyCheckBoxes;
    var registry = require('web.field_registry');

    var VariantsMany2ManyCheckBoxes = FieldMany2ManyCheckBoxes.extend({
        template: 'VariantsMany2ManyCheckBoxes',
        className: "o_field_variants_many2many_checkboxes",
    });

    registry.add('variant_many2many_checkboxes', VariantsMany2ManyCheckBoxes)
})