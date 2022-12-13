odoo.define('omniborders.HistoryBackAction', function (require) {
    "use strict";

    const core = require('web.core');
    const AbstractAction = require('web.AbstractAction');

    const HistoryBackAction = AbstractAction.extend({
        start: function() {
            this.trigger_up('history_back');
        }
    });

    core.action_registry.add("history_back", HistoryBackAction);

    return HistoryBackAction;
});
