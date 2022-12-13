odoo.define('omni_manage_channel.ImportProductChannelAction', function (require) {
    "use strict";
    /*global moment */

    const core = require('web.core');
    const framework = require('web.framework');
    const AbstractAction = require('web.AbstractAction');
    const DateTimeWidget = require('web.datepicker').DateTimeWidget;
    const Dialog = require('web.Dialog');
    const time = require('web.time');
    const _t = core._t;

    const { Component } = owl;
    const { useState } = owl.hooks;

    class StateImportComponent extends Component {

    }

    StateImportComponent.template = 'StateImportComponent';

    class ComponentImportProductChannel extends Component {

        constructor(parent, props) {
            super(null, props);
            this.parentWidget = parent;
            this.props = props || {};
            this.state = useState({
                is_in_syncing: false,
                is_done: false,
                is_error: false,
                option: null,
                is_confirmed: false,
                time_range_start_date: props.last_sync_product,
                time_range_end_date: moment().local().format(time.getLangDatetimeFormat()),
                auto_create_master: props.auto_create_master,
            });
        }

        mounted() {
            super.mounted(...arguments);
            this.attachDateWidgetsToTimeRangeOption();
        }

        attachDateWidgetsToTimeRangeOption() {
            const widgetsAndSections = _.object(_.map($(this.el).find('.time_range_datetime .datetime_picker'), (el) => {
                return [$(el).data('timePoint'), [new DateTimeWidget(this), el]];
            }));
            const appended = _.map(widgetsAndSections, (widgetsAndSection) => {
                const [widget, el] = widgetsAndSection;
                return widget.appendTo($(el));
            });
            Promise.all(appended).then(() => {
                _.map(widgetsAndSections, (widgetsAndSection, timePoint) => {
                    const widget = widgetsAndSection[0];
                    widget.$input.addClass('required');
                    widget.$input.val(this.state[timePoint]).trigger('change');
                    widget.on('datetime_changed', widget, () => {
                        const value = widget.getValue();
                        this.state[timePoint] = value ? value.format(time.getLangDatetimeFormat()) : '';
                    })
                });
            });
        }

        disableDateWidgetsToTimeRange() {
            $(this.el).find('.time_range_datetime .datetime_picker input').prop('disabled', true);
        }

        onDownload() {
            const msg = this.validateInput();
            if (!msg) {
                this.state.is_in_syncing = true;
                this.disableDateWidgetsToTimeRange()
                const autoCreateMaster = this.state['auto_create_master'] || false;
                const criteria = this.buildImportationCriteria();
                this.parentWidget.onDownload(this.state.option, autoCreateMaster, criteria);
            }
            else {
                this.alertValidationError(msg);
            }
        }
        buildImportationCriteria() {
            const criteria = {};
            if (this.state.option === 'time_range') {
                criteria['date_modified_str'] = time.datetime_to_str(this.timeRangeStart.toDate());
                criteria['to_date_str'] = time.datetime_to_str(this.timeRangeEnd.toDate());
            }
            if (this.state.option === 'product_ids') {
                criteria['ids_csv'] = this.state['import_product_ids']
            }
            return criteria;
        }
        alertValidationError(msg) {
            const dialog = Dialog.alert(this, _t(msg), {
                title: _t('Validation Error'),
            });
            dialog.opened().then(() => {
                dialog.$modal.css({'padding': '10rem 0'})
            });
        }

        validateInput() {
            if (this.state.option === 'time_range') {
                if (!this.timeRangeStart.isValid() || !this.timeRangeEnd.isValid()) {
                    return 'From Date and To Date are required!';
                }
                if (this.timeRangeStart >= this.timeRangeEnd) {
                    return 'To Date must be after From Date!';
                }
            }
            if (this.state.option === 'product_ids') {
                if (!this.state['import_product_ids']) {
                    return 'Product IDs cannot be empty'
                }
            }
        }

        get timeRangeStart() {
            return this.timeRangePoint('start');
        }
        get timeRangeEnd() {
            return this.timeRangePoint('end');
        }
        timeRangePoint(point) {
            return moment(this.state[`time_range_${point}_date`], time.getLangDatetimeFormat());
        }

        onClose(ev){
            this.parentWidget.onClose();
        }

    }

    ComponentImportProductChannel.components = { StateImportComponent };
    ComponentImportProductChannel.template = 'ImportProductChannelComponent';

    const ImportProductChannelAction = AbstractAction.extend({
        contentTemplate: "omni_manage_channel.ImportProductChannelAction",

        init: function(parent, options){
            this._super.apply(this, arguments);
            let last_sync_product = options.context.last_sync_product;
            if(last_sync_product) {
                last_sync_product = moment.utc(last_sync_product).local().format('MM/DD/YYYY HH:mm:ss');
            }
            this.props = {
                channel_platform: options.context.channel_platform,
                channel_platform_display: _.str.titleize(options.context.channel_platform),
                channel_name: options.context.channel_name,
                fields: options.context.fields,
                channel_id: options.context.channel_id,
                options: options.context.options,
                last_option_sync_product: options.context.last_option_sync_product,
                last_sync_product: last_sync_product,
                auto_create_master: options.context.auto_create_master,
                product_ids_option_note: options.context.product_ids_option_note,
            };

            if (this.props.last_option_sync_product){
                this.isDone();
            }
        },

        willStart: function () {
            const proms = [this._super.apply(this, arguments)];
            if (!this.props.channel_id) {
                window.location.href = '/web'
            }
            return Promise.all(proms);
        },

        start() {
            this._super.apply(this, arguments);
            this.mountImportationComponent();
        },

        mountImportationComponent() {
            const container = this.el.getElementsByClassName("o_import_product_action")[0];
            this.templateImport = new ComponentImportProductChannel(this, this.props);
            this.templateImport.mount(container);
        },

        onClose(){
            const self = this;
            this._rpc({
                method: 'close_import_product',
                model: 'ecommerce.channel',
                args: [[this.props.channel_id]]
            }).then(function(action){
                self.do_action(action);
            })
        },

        onDownload: function(option, autoCreateMaster, criteria){
            const self = this;
            framework.blockUI();
            this.$el.scrollTo(0, 0);
            this._rpc({
                method: 'import_product',
                model: 'ecommerce.channel',
                args: [[this.props.channel_id], option],
                kwargs: {
                    auto_create_master: autoCreateMaster,
                    criteria: criteria,
                }
            }).then(function(flag){
                if (flag === false){
                    self.call('crash_manager', 'show_warning', {
                        message: _t("Your channel has been disconnected. Please contact your administrator."),
                        title: _t("Access Denied"),
                    }, {
                        sticky: false,
                    });
                    return false
                }
                self.$el.find("ol.steps li").removeClass('not-done');
                self.isDone();
                framework.unblockUI();
            }).guardedCatch(framework.unblockUI);
        },
        isDone: function(){
            const self = this;
            this.checkingTimer = setInterval(function () {
                self._rpc({
                    method: 'is_importing_done',
                    model: 'ecommerce.channel',
                    args: [[self.props.channel_id]]
                }).then(function(result){
                    if (result['success'] === true){
                        self.templateImport.state.is_in_syncing = false;
                        self.templateImport.state.is_done = true;
                        clearInterval(self.checkingTimer);
                    }else if (result['error'] === true) {
                        self.templateImport.state.is_in_syncing = false;
                        self.templateImport.state.is_error = true;
                        clearInterval(self.checkingTimer);
                    }
                    self.$el.scrollTo(0, 0);
                })
            }, 30000);
        },
    });

    core.action_registry.add('action.import_product_channel', ImportProductChannelAction);

    return {
        StateImportComponent: StateImportComponent,
        ComponentImportProductChannel: ComponentImportProductChannel,
        ImportProductChannelAction: ImportProductChannelAction,
    };
});
