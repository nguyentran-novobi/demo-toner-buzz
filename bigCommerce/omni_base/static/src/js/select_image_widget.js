odoo.define('omni_base.Many2OneImage', function (require) {
    "use strict";

    var FieldMany2One = require('web.relational_fields').FieldMany2One;
    var session = require('web.session');
    var registry = require('web.field_registry');
    var core = require('web.core');
    var qweb = core.qweb;
    var SelectCreateDialog = require('web.view_dialogs').SelectCreateDialog;

    var SelectImageDialog = SelectCreateDialog.extend({
        init: function () {
            this._super.apply(this, arguments);
            this.viewType = 'kanban';
        },
        opened: function(){
            let self = this;
            return Promise.all([this._super.apply(this, arguments)]).then(function () {
                $(_.last($('.modal-backdrop'))).css('z-index', 1090);
                $(_.last($('.modal'))).css('z-index', 2000);
                self.$el.find('.o_cp_searchview').css('visibility', 'hidden');
                self.$el.find('.o_search_options').css('visibility', 'hidden');
            })
        }
    });

    var Many2OneImage = FieldMany2One.extend({
        template: 'Many2OneImage',
        placeholder: "/web/static/src/img/placeholder.png",
        events: _.extend({}, FieldMany2One.prototype.events, {
            'click .o_select_file_button': '_onSelectImage',
            'click .o_clear_file_button': '_onClearImage'
        }),
        _getImageUrl: function(model, res_id, field){
            return session.url('/web/image', {
                model: model,
                id: JSON.stringify(res_id),
                field: field,
            });
        },
        _render: function () {
            this._super.apply(this, arguments);
            let url = this.placeholder;
            if (this.value) {
                url = this._getImageUrl(this.field.relation, this.value.res_id, 'image');
            }
            var $img = $(qweb.render("Many2OneImage-img", {widget: this, url: url}));
            var width = this.nodeOptions.size ? this.nodeOptions.size[0] : this.attrs.width;
            var height = this.nodeOptions.size ? this.nodeOptions.size[1] : this.attrs.height;
            if (width) {
                $img.attr('width', width);
                $img.css('max-width', width + 'px');
            }
            if (height) {
                $img.attr('height', height);
                $img.css('max-height', height + 'px');
            }
            this.$('> img').remove();
            this.$el.prepend($img);
        },
        /**
         * @private
         */
        _renderEdit: function () {

        },
        /**
         * @private
         */
        _renderReadonly: function () {

        },
        _onSelectImage: function(){
            let self = this;
            let options = {
                res_model: this.field.relation,
                domain: this.record.getDomain(this.recordParams),
                context: _.extend({}, this.record.getContext(this.recordParams),{}),
                title: 'Select Image',
                viewType: 'kanban',
                disable_multiple_selection: true,
                no_create: !this.can_create,
                on_selected: function (records) {
                    self.reinitialize(records[0]);
                },
                on_closed: function () {
                    self.activate();
                },
            };
            new SelectImageDialog(this, _.extend({}, this.nodeOptions, options)).open();
       },
        _onClearImage: function () {
            this.reinitialize(false);
        }
    });

    registry
    .add('many2one_image', Many2OneImage)
});
