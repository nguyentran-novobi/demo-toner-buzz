odoo.define('omni_manage_channel.channel_many2one', function (require) {
    'use strict';

    var FieldMany2One = require('web.relational_fields').FieldMany2One;
    var field_registry = require('web.field_registry');
    var core = require('web.core');
    var qweb = core.qweb;

    var ChannelField = FieldMany2One.extend({

        _getImageSrc: function(label){
            let begin = label.indexOf("[");
            let end = label.indexOf("]");
            let platform = label.substring(begin, end+1);
            let title = label.replace(platform, '');
            platform = platform.replace("[", "").replace("]", "").toLowerCase();
            let src = ''
            if (platform != ''){
                src = "/omni_manage_channel/static/src/img/" + platform + ".png"
            }
            return [title, src];
        },
        
        _modifyAutompleteRendering: function (){
            let self = this;
            var api = this.$input.data('ui-autocomplete');
            // FIXME: bugfix to prevent traceback in mobile apps due to override
            // of Many2one widget with native implementation.
            if (!api) {
                return;
            }
            api._renderItem = function(ul, item){
                ul.addClass('o_channel_autocomplete_dropdown');
                let values = self._getImageSrc(item.label);
                var $a = $('<a/>')["html"](values[0]);
                if (values[1]){
                    let $img = $("<img width='30' style='margin:5px'/>").attr('src', values[1]);
                     $a.prepend($img);
                }
                return $("<li></li>")
                    .data("item.autocomplete",item)
                    .append($a)
                    .appendTo(ul)
                    .addClass(item.classname);
            };
        },

        _renderReadonly: function () {
            var escapedValue = _.escape((this.m2o_value || "").trim());
            let values = this._getImageSrc(escapedValue);
            this.image_url = values[1];
            this.m2o_value = values[0];
            this.$el.html(qweb.render("ChannelMany2one.Readonly", {widget: this}))
        },

        _renderEdit: function () {
            this._super.apply(this, arguments);
            let values = this._getImageSrc(this.$input.val());
            this.$input.val(values[0]);
            if (values[1]){
                if (this.$image == undefined){
                    this.$image = $("<img />").attr('src', values[1]);
                    this.$image.css({'position': 'absolute', 'height':20, 'min-height':20, 'max-width': 35});
                    this.$input.css({'padding-left': '30px'});
                    this.$input.parent().prepend(this.$image);
                }else{
                    this.$image.attr('src', values[1]);
                }
            }
        },

        _bindAutoComplete: function () {
            this._super.apply(this, arguments);
            this._modifyAutompleteRendering();
        }
    });

    field_registry.add('channel_many2one', ChannelField);

    return ChannelField;
})