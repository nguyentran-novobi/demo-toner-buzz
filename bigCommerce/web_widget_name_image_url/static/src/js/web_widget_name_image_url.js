odoo.define('web_widget_name_image_url.FieldNameImageURL', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var core = require('web.core');
    var registry = require('web.field_registry');
    var _t = core._t;

    var FieldNameImageURL = AbstractField.extend({
        className: 'o_attachment_image',
        template: 'FieldNameImageURL',
        placeholder: "/web/static/src/img/placeholder.png",
        supportedFieldTypes: ['many2many', 'many2one'],
        fieldsToFetch: {
            display_name: {type: 'char'},
            image_url : {type: 'char'}
        },

        init: function (parent, name, record, options) {
            var self = this;
            this._super.apply(this, arguments);
            this.custom_tags = [];
            if (this.value){
                if (this.formatType == 'many2many'){
                    _.each(this.value.data, function(e){
                        var begin = e.data.display_name.indexOf("[");
                        var end = e.data.display_name.indexOf("]");
                        if (begin != -1 && end != -1){
                            var platform = e.data.display_name.substring(begin, end+1);
                            self.custom_tags.push({image_url:e.data.image_url, name:e.data.display_name.replace(platform, '').trim()})
                        }
                        else{
                            self.custom_tags.push({image_url:null, name:e.data.display_name.trim()})
                        }
                    })
                }
                else{
                    var begin = this.value.data.display_name.indexOf("[");
                    var end = this.value.data.display_name.indexOf("]");
                    if (begin != -1 && end != -1){
                        var platform = this.value.data.display_name.substring(begin, end+1);
                        var image_url = '/omni_manage_channel/static/src/img/'+platform.replace('[','').replace(']','').toLowerCase()+'.png';
                        this.custom_tags.push({image_url:image_url, name:this.value.data.display_name.replace(platform, '').trim()})
                    }
                    else{
                        this.custom_tags.push({image_url:null, name:this.value.data.display_name.trim()})

                    }
                }
            }
        },
        _render: function () {
            this._super(arguments);

            var self = this;
            var $img = this.$("img:first");
            $img.on('error', function () {
                $img.attr('src', self.placeholder);
                self.do_warn(
                    _t("Image"), _t("Could not display the selected image."));
            });
        },
    });

    registry.add('name_image_url', FieldNameImageURL);
});
