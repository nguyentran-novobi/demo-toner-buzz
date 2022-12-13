odoo.define('omni_base.BooleanButton', function (require) {
'use strict';


    const AbstractField = require('web.AbstractFieldOwl');
    const registry = require('web.field_registry_owl');
    const { _lt } = require('web.translation');

    class FieldBooleanButton extends AbstractField {

        constructor() {
            super(...arguments);

            let text, hover;
            switch (this.nodeOptions.terminology) {
                case "active":
                    text = this.value ? _lt("Active") : _lt("Inactive");
                    hover = this.value ? _lt("Deactivate") : _lt("Activate");
                    break;
                case "archive":
                    text = this.value ? _lt("Active") : _lt("Archived");
                    hover = this.value ? _lt("Archive") : _lt("Restore");
                    break;
                case "close":
                    text = this.value ? _lt("Active") : _lt("Closed");
                    hover = this.value ? _lt("Close") : _lt("Open");
                    break;
                default:
                    let opt_terms = this.nodeOptions.terminology || {};
                    if (typeof opt_terms === 'string') {
                        opt_terms = {}; //unsupported terminology
                    }
                    text = this.value ? _lt(opt_terms.string_true) || _lt("On")
                                      : _lt(opt_terms.string_false) || _lt("Off");
                    hover = this.value ? _lt(opt_terms.hover_true) || _lt("Switch Off")
                                       : _lt(opt_terms.hover_false) || _lt("Switch On");
            }
            let text_color = this.value ? 'text-success' : 'text-danger';
            let hover_color = this.value ? 'text-danger' : 'text-success';

            this.props = Object.assign(this.props, {text: text,
                hover: hover, text_color: text_color, hover_color: hover_color});
        }
        /**
         * A boolean field is always set since false is a valid value.
         *
         * @override
         */
        get isSet() {
            return true;
        }

        //----------------------------------------------------------------------
        // Handlers
        //----------------------------------------------------------------------

    }

    FieldBooleanButton.template = 'omni_base.FieldBooleanButton';
    FieldBooleanButton.supportedFieldTypes = ['boolean'];

    registry
        .add('boolean_button', FieldBooleanButton);
    });
