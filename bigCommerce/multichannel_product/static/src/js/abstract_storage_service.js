odoo.define('multichannel_product.AbstractStorageService', function (require) {
'use strict';
    var AbstractStorageService = require('web.AbstractStorageService');
    AbstractStorageService.include({
        setItem: function(key, value) {
            try{
                this.storage.setItem(key, JSON.stringify(value));
            }catch(err){

            }
        },
    })
})