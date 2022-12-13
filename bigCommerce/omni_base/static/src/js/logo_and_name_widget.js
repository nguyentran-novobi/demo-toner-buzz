odoo.define('omni_base.logo_and_name', function (require) {
    "use strict";

    const AbstractField = require('web.AbstractFieldOwl');
    const registry = require('web.field_registry_owl');

    class LogoAndName extends AbstractField {
        constructor(){
            super(...arguments);
            this.props.data = JSON.parse(this.value);
        }
    }

    LogoAndName.template = 'omni_base.LogoAndName';
    LogoAndName.supportedFieldTypes = ['char'];

    registry
        .add('logo_and_name', LogoAndName);

})