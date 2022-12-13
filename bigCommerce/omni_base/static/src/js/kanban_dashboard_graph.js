odoo.define('omni_base.kanban_dashboard_graph', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var registry = require('web.field_registry');

    var field_utils = require('web.field_utils');
    var session = require('web.session');

    var FORMAT_OPTIONS = {
        // allow to decide if utils.human_number should be used
        humanReadable: function (value) {
            return Math.abs(value) >= 1000;
        },
        // with the choices below, 1236 is represented by 1.24k
        minDigits: 1,
        decimals: 2,
        // avoid comma separators for thousands in numbers when human_number is used
        formatterCallback: function (str) {
            return str;
        },
    };

    var KanbanDashboardGraph = AbstractField.extend({
        className: "o_kanban_dashboard_graph",
        jsLibs: [
            '/web/static/lib/Chart/Chart.js',
        ],
        init: function () {
            this._super.apply(this, arguments);
            this.graph_type = this.attrs.graph_type;
            this.data = JSON.parse(this.value);
            this.backgroundColor = this.attrs.background_color;
            this.borderColor = this.attrs.border_color;
            this.displayLabelXY = (this.attrs.display_label_xy == 'True') | false;
            this.fillArea = (this.attrs.fill_area == 'True') | false;
            this.displayLegend = (this.attrs.display_legend == 'True') | false;
            this.displayCurrency = this.attrs.display_currency == 'True';
            if (this.data){
                this.currency_id = this.data[0].currency.id;
            }  
        },
        /**
         * The widget view uses the ChartJS lib to render the graph. This lib
         * requires that the rendering is done directly into the DOM (so that it can
         * correctly compute positions). However, the views are always rendered in
         * fragments, and appended to the DOM once ready (to prevent them from
         * flickering). We here use the on_attach_callback hook, called when the
         * widget is attached to the DOM, to perform the rendering. This ensures
         * that the rendering is always done in the DOM.
         */
        on_attach_callback: function () {
            this._isInDOM = true;
            this._renderInDOM();
        },
        /**
         * Called when the field is detached from the DOM.
         */
        on_detach_callback: function () {
            this._isInDOM = false;
        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * Render the widget only when it is in the DOM.
         *
         * @override
         * @private
         */
        _render: function () {
            if (this._isInDOM) {
                return this._renderInDOM();
            }
            return Promise.resolve();
        },
        /**
         * Render the widget. This function assumes that it is attached to the DOM.
         *
         * @private
         */
        _renderInDOM: function () {
            this.$el.empty();
            var config, cssClass;
            if (this.data){
                if (this.graph_type === 'line') {
                    config = this._getLineChartConfig();
                    cssClass = 'o_graph_linechart';
                } else if (this.graph_type === 'bar') {
                    config = this._getBarChartConfig();
                    cssClass = 'o_graph_barchart';
                }
                this.$canvas = $('<canvas/>');
                this.$el.addClass(cssClass);
                this.$el.empty();
                this.$el.append(this.$canvas);
                var context = this.$canvas[0].getContext('2d');
                this.chart = new Chart(context, config);
            }
        },
        render_monetary_field: function(value, currency_id) {
            var currency = session.get_currency(currency_id);
            var formatted_value = field_utils.format.float(value || 0, {digits: currency && currency.digits});
            if (currency) {
                if (currency.position === "after") {
                    formatted_value += currency.symbol;
                } else {
                    formatted_value = currency.symbol + formatted_value;
                }
            }
            return formatted_value;
        },
        format_currency: function(amount){
            var currency = session.get_currency(this.currency_id);
            var formatted_value = field_utils.format.float(amount || 0, {digits: currency && currency.digits}, FORMAT_OPTIONS);
            if (currency) {
                if (currency.position === "after") {
                    formatted_value += currency.symbol;
                } else {
                    formatted_value = currency.symbol + formatted_value;
                }
            }
            return formatted_value;
        },
        _getLineChartConfig: function () {
            var self = this;
            var labels = this.data[0].values.map(function (pt) {
                return pt.x;
            });
            var borderColor = this.borderColor ? this.borderColor : '#875a7b';
            var backgroundColor = this.backgroundColor ? this.backgroundColor : '#dcd0d9';

            return {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        data: this.data[0].values,
                        fill: this.fillArea,
                        label: this.data[0].key,
                        backgroundColor: backgroundColor,
                        borderColor: borderColor,
                        borderWidth: 2,
                    }]
                },
                options: {
                    legend: {display: this.displayLegend},
                    scales: {
                        yAxes: [{
                            display: this.displayLabelXY,
                            ticks: {
                                // Include a dollar sign in the ticks
                                callback: function(value, index, values) {
                                    if (self.displayCurrency){
                                        value = self.format_currency(parseFloat(value))
                                    }
                                    return value;
                                },
                                autoSkip: true,
                                min: 0,
                            }
                        }],
                        xAxes: [{
                            display: this.displayLabelXY,
                            // type: 'time',
                            // time: {
                            //     unit: 'week'
                            // }
                        }]
                    },
                    maintainAspectRatio: false,
                    elements: {
                        line: {
                            tension: 0.000001
                        }
                    },
                    tooltips: {
                        intersect: false,
                        position: 'nearest',
                        caretSize: 0,
                        enabled: true,
					    mode: 'single',
                        callbacks: {
                            label: function(tooltipItems, data) {
                                var multistringText = [];
                                multistringText.push('Total Sales: ' + self.format_currency(tooltipItems.yLabel));
                                return multistringText;
                            }
                        }
                    },
                },
            };
        },
        _getBarChartConfig: function () {
            var data = [];
            var labels = [];
            var backgroundColor = [];

            this.data[0].values.forEach(function (pt) {
                data.push(pt.value);
                labels.push(pt.label);
                var color = pt.type === 'past' ? '#ccbdc8' : (pt.type === 'future' ? '#a5d8d7' : '#ebebeb');
                backgroundColor.push(color);
            });
            return {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        data: data,
                        fill: this.fillArea,
                        label: this.data[0].key,
                        backgroundColor: backgroundColor,
                    }]
                },
                options: {
                    legend: {display: this.displayLegend},
                    scales: {
                        yAxes: [{display: this.displayLabelXY}],
                    },
                    maintainAspectRatio: false,
                    tooltips: {
                        intersect: false,
                        position: 'nearest',
                        caretSize: 0,
                    },
                    elements: {
                        line: {
                            tension: 0.000001
                        }
                    },
                },
            };
        },
    });

    registry.add('kanban_dashboard_graph', KanbanDashboardGraph)
})