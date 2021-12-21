/**
 * Amsify Jquery Select 1.1
 * https://github.com/amsify42/jquery.amsify.suggestags
 * http://www.amsify42.com
 */
(function($) {

    $.fn.amsifySuggestags = function(options, method) {
        /**
         * Merging default settings with custom
         * @type {object}
         */
        var settings = $.extend({
            type          : 'bootstrap',
            tagLimit      : -1,
            suggestions   : [],
            classes       : [],
            backgrounds   : [],
            colors        : [],
            whiteList     : false,
            afterAdd      : {},
            afterRemove   : {},
        }, options);

        /**
         * Initialization begins from here
         * @type {Object}
         */
        var AmsifySuggestags = function() {
            this.selector      = null;
            this.name          = null;
            this.defaultLabel  = 'Type here';
            this.classes       = {
              sTagsArea     : '.amsify-suggestags-area',
              inputArea     : '.amsify-suggestags-input-area',
              inputAreaDef  : '.amsify-suggestags-input-area-default',
              focus         : '.amsify-focus',
              sTagsInput    : '.amsify-suggestags-input',
              listArea      : '.amsify-suggestags-list',
              list          : '.amsify-list',
              listItem      : '.amsify-list-item',
              itemPad       : '.amsify-item-pad',
              inputType     : '.amsify-select-input',
              tagItem       : '.amsify-select-tag',
              colBg         : '.col-bg',
              removeTag     : '.amsify-remove-tag',
              readyToRemove : '.ready-to-remove',
           };
           this.selectors     = {
              sTagsArea     : null,
              inputArea     : null,
              inputAreaDef  : null,
              sTagsInput    : null,
              listArea      : null,
              list          : null,
              listGroup     : null,
              listItem      : null,
              itemPad       : null,
              inputType     : null,
           };
           this.tagNames = [];
        };

        AmsifySuggestags.prototype = {
            /**
             * Executing all the required settings
             * @param  {selector} form
             */
            _init : function(selector) {
                if(this.refresh(selector, method)) {
                  this.selector   = selector;
                  this.name       = ($(selector).attr('name'))? $(selector).attr('name')+'_amsify': 'amsify_suggestags';
                  this.createHTML();
                  this.setEvents();
                  $(this.selector).hide();
                  this.setDefault();
                }
            },

            createHTML : function() {
              var HTML                      = '<div class="'+this.classes.sTagsArea.substring(1)+'"></div>';
              this.selectors.sTagsArea      = $(HTML).insertAfter(this.selector);
              var labelHTML                 = '<div class="'+this.classes.inputArea.substring(1)+'"></div>';
              this.selectors.inputArea      = $(labelHTML).appendTo(this.selectors.sTagsArea);

              this.defaultLabel             = ($(this.selector).attr('placeholder') !== undefined)? $(this.selector).attr('placeholder'): this.defaultLabel;
              var sTagsInput                = '<input type="text" class="'+this.classes.sTagsInput.substring(1)+'" placeholder="'+this.defaultLabel+'">';
              this.selectors.sTagsInput     = $(sTagsInput).appendTo(this.selectors.inputArea).attr('autocomplete', 'off');

              var listArea              = '<div class="'+this.classes.listArea.substring(1)+'"></div>';
              this.selectors.listArea   = $(listArea).appendTo(this.selectors.sTagsArea);
              $(this.selectors.listArea).width($(this.selectors.sTagsArea).width()-3);

              var list                  = '<ul class="'+this.classes.list.substring(1)+'"></ul>';
              this.selectors.list       = $(list).appendTo(this.selectors.listArea);
              $(this.createList()).appendTo(this.selectors.list);
              this.fixCSS();
            },           

            setEvents : function() {
              var _self = this;
              $(this.selectors.inputArea).attr('style', $(this.selector).attr('style'))
                                         .addClass($(this.selector).attr('class'));
              $(this.selectors.sTagsInput).focus(function(){
                $(this).closest(_self.classes.inputArea).addClass(_self.classes.focus.substring(1));
                if(settings.type == 'materialize') {
                  $(this).css({
                    'border-bottom': 'none',
                    '-webkit-box-shadow': 'none',
                    'box-shadow': 'none',
                  });
                }
              });
              $(this.selectors.sTagsInput).blur(function(){
                $(this).closest(_self.classes.inputArea).removeClass(_self.classes.focus.substring(1));
              });
              $(this.selectors.sTagsInput).keyup(function(e){
                var keycode = (e.keyCode ? e.keyCode : e.which);
                if(keycode == '13' || keycode == '188') {
                   var value = $.trim($(this).val().replace(/,/g , ''));
                   $(this).val('');
                  _self.addTag(value);
                } else if(keycode == '8' && !$(this).val()) {
                  var removeClass = _self.classes.readyToRemove.substring(1);
                  if($(this).hasClass(removeClass)) {
                    $item = $(this).closest(_self.classes.inputArea).find(_self.classes.tagItem+':last');
                    _self.removeTag($item, false);
                    $(this).removeClass(removeClass);
                  } else {
                    $(this).addClass(removeClass);
                  }
                } else if(settings.suggestions.length && $(this).val()) {
                  $(this).removeClass(_self.classes.readyToRemove.substring(1));
                  _self.processWhiteList(keycode, $(this).val());
                }
              });
              $(window).resize(function(){
                $(_self.selectors.listArea).width($(_self.selectors.sTagsArea).width()-3);
              });
              $(this.selectors.sTagsArea).click(function(){
                $(_self.selectors.sTagsInput).focus();
              });
              $(this.selectors.listArea).find(this.classes.listItem).hover(function(){
                $(_self.selectors.listArea).find(_self.classes.listItem).removeClass('active');
                $(this).addClass('active');
                $(_self.selectors.sTagsInput).val($(this).data('val'));
              }, function() {
                 $(this).removeClass('active');
              });
              $(this.selectors.listArea).find(this.classes.listItem).click(function(){
                 _self.addTag($(this).data('val'));
                 $(_self.selectors.sTagsInput).val('').focus();
              });
              this.setRemoveEvent();
            },

            processWhiteList : function(keycode, value) {
              if(keycode == '40' || keycode == '38') {
                var type = (keycode == '40')? 'down': 'up';
                this.upDownSuggestion(value, type);
              } else {
                this.suggestWhiteList(value);
              }
            },

            upDownSuggestion : function(value, type) {
              var _self     = this;
              var isActive  = false;
              $(this.selectors.listArea).find(this.classes.listItem+':visible').each(function(){
                   if($(this).hasClass('active')) {
                    $(this).removeClass('active');
                      if(type == 'up') {
                        $item = $(this).prevAll(_self.classes.listItem+':visible:first');
                      } else {
                        $item = $(this).nextAll(_self.classes.listItem+':visible:first');
                      }
                      if($item.length) {
                        isActive = true;
                        $item.addClass('active');
                        $(_self.selectors.sTagsInput).val($item.data('val'));
                      }
                    return false;
                   }
              });
              if(!isActive) {
                var childItem = (type == 'down')? 'first': 'last';
                $item = $(this.selectors.listArea).find(this.classes.listItem+':visible:'+childItem);
                if($item.length) {
                  $item.addClass('active');
                  $(_self.selectors.sTagsInput).val($item.data('val'));
                }
              }
            },

            suggestWhiteList : function(value) {
              var _self = this;
              var found = false;
              $(this.selectors.listArea).find(this.classes.listItem).each(function(){
                if(~$(this).attr('data-val').toLowerCase().indexOf(value.toLowerCase()) && $.inArray($(this).attr('data-val'), _self.tagNames) === -1) {
                  $(this).show();
                  found = true;
                } else {
                  $(this).hide();
                }
              });
              if(found)
                $(this.selectors.listArea).show();
              else
                $(this.selectors.listArea).hide();
            },

            setDefault : function() {
              var _self = this;
              var items = $(this.selector).val().split(',');
              if(items.length) {
                $.each(items, function(index, item){
                  _self.addTag($.trim(item));
                });
              }
            },

            setRemoveEvent: function() {
              var _self = this;
              $(this.selectors.inputArea).find(this.classes.removeTag).click(function(e){
                  e.stopImmediatePropagation();
                  $tagItem = $(this).closest(_self.classes.tagItem);
                  _self.removeTag($tagItem, false);
              });
            },

            createList : function() {
              var _self     = this;
              var listHTML  = '';
              $.each(settings.suggestions, function(index, item){
                  listHTML += '<li class="'+_self.classes.listItem.substring(1)+'" data-val="'+item+'">'+item+'</li>';
              });
              return listHTML;
            },

            addTag : function(value) {
              if(!value) return;
              var html  = '<span class="'+this.classes.tagItem.substring(1)+'" data-val="'+value+'">'+value+' '+this.setIcon()+'</span>';
              $item = $(html).insertBefore($(this.selectors.sTagsInput));
              if(settings.tagLimit != -1 && settings.tagLimit > 0 && this.tagNames.length >= settings.tagLimit) {
              	this.animateRemove($item, true);
                this.flashItem(value);
                return false;
              }
              var itemKey = $.inArray(value, settings.suggestions);
              if(settings.whiteList && itemKey === -1) {
                this.animateRemove($item, true);
                this.flashItem(value);
                return false;
              }
              if(this.isPresent(value)) {
                this.animateRemove($item, true);
                this.flashItem(value);
              } else {
                this.customStylings($item, itemKey);
                this.tagNames.push(value);
                this.setRemoveEvent();
                this.setInputValue();
                if(settings.afterAdd && typeof settings.afterAdd == "function") {
                  settings.afterAdd(value);
                }
              }
              $(this.selector).trigger('suggestags.add', [value]);
              $(this.selectors.listArea).find(this.classes.listItem).removeClass('active');
              $(this.selectors.listArea).hide();
            },

            isPresent : function(value) {
              var present = false;
              $.each(this.tagNames, function(index, tag){
                if(value.toLowerCase() == tag.toLowerCase()) {
                  present = true;
                  return false;
                }
              });
              return present;
            },

            customStylings : function(item, key) {
              var isCutom = false;
              if(settings.classes[key]) {
                isCutom = true;
                $(item).addClass(settings.classes[key]);
              }
              if(settings.backgrounds[key]) {
                isCutom = true;
                $(item).css('background', settings.backgrounds[key]);
              }
              if(settings.colors[key]) {
                isCutom = true;
                $(item).css('color', settings.colors[key]);
              }
              if(!isCutom) $(item).addClass(this.classes.colBg.substring(1));
            },

            removeTag : function(item, animate) {
              this.tagNames.splice($(item).index(), 1);
              this.animateRemove(item, animate);
              this.setInputValue();
              $(this.selector).trigger('suggestags.remove', [$(item).attr('data-val')]);
              if(settings.afterRemove && typeof settings.afterRemove == "function") {
                settings.afterRemove($(item).attr('data-val'));
              }
            },

            animateRemove : function(item, animate) {
              $(item).addClass('disabled');
              if(animate) {
                setTimeout(function(){
                  $(item).slideUp();
                  setTimeout(function(){
                    $(item).remove();
                  }, 500);
                }, 500);
              } else {
                $(item).remove();
              }
            },

            flashItem : function(value) {
              $item  = '';
              $(this.selectors.sTagsArea).find(this.classes.tagItem).each(function(){
                var tagName = $.trim($(this).attr('data-val'));
                if(value.toLowerCase() == tagName.toLowerCase()) {
                  $item = $(this);
                  return false;
                }
              });
              if($item) {
                $item.addClass('flash');
                setTimeout(function(){
                  $item.removeClass('flash');
                }, 1500);
              }
            },

            setIcon : function() {
              var removeClass = this.classes.removeTag.substring(1);
              if(settings.type == 'bootstrap') {
                return '<span class="fa fa-times '+removeClass+'"></span>';
              } else if(settings.type == 'materialize') {
                return '<i class="material-icons right '+removeClass+'">clear</i>';
              } else {
                return '<b class="'+removeClass+'">&#10006;</b>';
              }
            },

            setInputValue: function() {
              $(this.selector).val(this.tagNames.join(','));
              this.printValues();
            },

            fixCSS : function() {
              if(settings.type == 'amsify') {
                $(this.selectors.inputArea).addClass(this.classes.inputAreaDef.substring(1)).css({'padding': '5px 5px'});
              } else if(settings.type == 'materialize') {
                $(this.selectors.inputArea).addClass(this.classes.inputAreaDef.substring(1)).css({'height': 'auto', 'padding': '5px 5px'});
                $(this.selectors.sTagsInput).css({'margin': '0', 'height': 'auto'});
              }
            },

            printValues : function() {
              console.info(this.tagNames, $(this.selector).val());
            },

            refresh : function(selector, method) {
              $findTags = $(selector).next(this.classes.sTagsArea);
              if($findTags.length)  $findTags.remove();
              $(selector).show();
              if(typeof method !== undefined && method == 'destroy') {
                return false;
              } else {
                return true;
              }
            },
           
        };
        
        /**
         * Initializing each instance of selector
         * @return {object}
         */
        return this.each(function() {
            (new AmsifySuggestags)._init(this);
        });

    };

}(jQuery));