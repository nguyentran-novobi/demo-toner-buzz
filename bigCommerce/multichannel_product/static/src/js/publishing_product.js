odoo.define('omniborders.PublishingProduct', function (require) {
    "use strict";

    const AbstractView = require('web.AbstractView');
    const core = require('web.core');
    const viewRegistry = require('web.view_registry');
    const ListView = require('web.ListView');
    const Dialog = require('web.Dialog');
    const ListController = require('web.ListController');
    const framework = require('web.framework');
    const _t = core._t;

    const ProductMappingListController = ListController.extend({
        do_notify: function (title = false, message, sticky, className) {
            return this.displayNotification({
                type: 'success',
                title: title,
                message: message,
                sticky: sticky,
                className: className,
            });
        },

        do_warn: function (title = false, message, sticky, className) {
            return this.displayNotification({
                type: 'danger',
                title: title,
                message: message,
                sticky: sticky,
                className: className,
            });
        },

        _getActionMenuItems: function (state) {
            const props = this._super(...arguments);
            if (props) {
                let otherActionItems = [{
                    description: _t(`Export to Store`),
                    callback: () => this._onPublish()
                }];
                return Object.assign(props, {
                    items: Object.assign({}, props.items, {
                        other: [...props.items.other, ...otherActionItems]
                    }),
                });
            }
            return props;
        },

        _onPublish: function() {
            const ids = this.getSelectedIds();
            if (ids.length === 0){
                this.do_warn(_t("Error"), _t("Please select product(s) to get started!"));
                return false
            }
            const message = _t('Are you sure you want to export selected product(s)?');
            Dialog.confirm(this, message, {
                confirm_callback: () => {
                    framework.blockUI();
                    this._rpc({
                        method: 'export_mappings_to_channel',
                        model: this.modelName,
                        args: [ids]
                    }).then((result) => {
                        if (ids.length > 1) {
                            this.do_notify(_t('Export Products'), _t('Your request is currently being processed'), false);
                        } else {
                            if (result['success']) {
                                this.do_notify(_t('Export Product'), _t('Your product is exported'), false);
                            } else {
                                this.do_warn(_t('Error'), _t(result['msg']), false);
                            }
                        }
                        framework.unblockUI();
                        this.trigger_up('reload');
                    }).guardedCatch(() => {
                        framework.unblockUI();
                        this.trigger_up('reload');
                    });
                }
            });
            return true
        }
    });

    const ProductMappingListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Controller: ProductMappingListController,
        }),
    });

    viewRegistry.add('product_mapping_list', ProductMappingListView);
});
