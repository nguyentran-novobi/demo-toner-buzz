odoo.define('omni_manage_channel.OnboardingAction', function (require) {
    "use strict";

    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var AbstractAction = require('web.AbstractAction');
    var _t = core._t;

    const { Component } = owl;
    const { useState, useRef } = owl.hooks;

    const NAME2MODEL = {
        product_template: 'product.template',
        customer_channel: 'customer.channel',
        sale_order: 'sale.order'
    }

    class ComponentOnboardingAction extends Component {

        constructor(parent, props) {
            super(null, props);
            this.parentWidget = parent;
            this.props = props || {};
            this.datas = ['product_template', 'customer_channel', 'sale_order'];
            this.state = useState({
                is_sync: false,
                is_processing: false,
                selected_option: false,
                data_sync: {
                    product_template: false,
                    customer_channel: false,
                    sale_order: false
                }
            });
            this.optionsRef = useRef('optionsRef');
        }
        mounted() {
            super.mounted(...arguments);
            let saleOption = this.optionsRef.el.querySelector('input#sale_order');
            saleOption.addEventListener('change', this._setAllOptions.bind(this));
        }
        _setAllOptions(ev){
            if (this.state.data_sync.sale_order){
                let self = this;
                _.each(this.datas, function(key){
                    self.state.data_sync[key] = true
                })
            }
        }
        _unsetAllOptions(){
            let self = this;
            _.each(this.datas, function(key){
                self.state.data_sync[key] = false
            })
        }
        render() {
            if (this.state.is_sync == 'no'){
                this._unsetAllOptions();
            }
            super.render(...arguments);
        }
        onSync(){
            var self = this;
            let data = _.filter(this.datas, function(key){ return self.state.data_sync[key]});
            data = _.map(data, function(e) { return NAME2MODEL[e]});
            this.parentWidget._rpc({
                method: 'run_onboarding',
                model: 'ecommerce.channel',
                args: [[this.props.channel_id], data],
            }).then(function(result){
                if (result['success'] == true){
                    self.state.is_processing = true;
                }else{
                    self.parentWidget.showError(result['error'])
                }
            })
        }

        onClose(){
            let self = this;
            this.parentWidget._rpc({
                method: 'button_close',
                model: 'ecommerce.channel',
                args: [[this.props.channel_id]]
            }).then(function(action){
                self.parentWidget.do_action(action);
            })
        }
    }

    ComponentOnboardingAction.template = 'OnboardingActionComponent';

    var OnboardingAction = AbstractAction.extend({
        contentTemplate: 'OnboardingAction',
        init: function(parent, options){
            this._super.apply(this, arguments);
            this.channel_id = options.context.params.id;
            this.props = {
                channel_id: options.context.params.id
            }
        },

        start() {
            this._super.apply(this, arguments);
            const container = this.el.getElementsByClassName("o_onboarding_action")[0];
            new ComponentOnboardingAction(this, this.props).mount(container);
        },

        showError: function(error){
            new Dialog(this, {
                title: _.str.capitalize(_t("Odoo Error")),
                $content: $(QWeb.render('CrashManager.error', {error: error}))
            })();
        }
    })

    core.action_registry.add('action.onboarding', OnboardingAction);

})