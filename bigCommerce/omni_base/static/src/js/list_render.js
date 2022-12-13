odoo.define('omni_base.ListRenderer', function (require) {
"use strict";

    var ListRenderer = require('web.ListRenderer');
    var AbstractView = require('web.AbstractView');

    AbstractView.include({
        init: function (viewInfo, params) {
            this._super.apply(this, arguments);
            this.controllerParams.activeActions.hasSelectors = params.context['hasSelectors'];
        }
    })

    ListRenderer.include({
        init: function (parent, state, params) {
            this._super.apply(this, arguments);
            if (params.activeActions && params.activeActions.hasSelectors != undefined){
                this.hasSelectors = params.activeActions.hasSelectors
            }
        },
    })
})