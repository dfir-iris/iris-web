ace.define("ace/theme/iris_night",["require","exports","module","ace/lib/dom"], function(require, exports, module) {

exports.isDark = true;
exports.cssClass = "ace-iris-night";
exports.cssText = ".ace-iris-night .ace_gutter {\
background: #181e2f;\
color: #C5C8C6\
}\
.ace-iris-night .ace_print-margin {\
width: 1px;\
background: #181e2f\
}\
.ace-iris-night {\
background-color: #1b2233;\
color: #C5C8C6\
}\
.ace-iris-night .ace_cursor {\
color: #AEAFAD\
}\
.ace-iris-night .ace_marker-layer .ace_selection {\
background: #373B41\
}\
.ace-iris-night.ace_multiselect .ace_selection.ace_start {\
box-shadow: 0 0 3px 0px #1b2233;\
}\
.ace-iris-night .ace_marker-layer .ace_step {\
background: rgb(102, 82, 0)\
}\
.ace-iris-night .ace_marker-layer .ace_bracket {\
margin: -1px 0 0 -1px;\
border: 1px solid #4B4E55\
}\
.ace-iris-night .ace_marker-layer .ace_active-line {\
background: #151926\
}\
.ace-iris-night .ace_gutter-active-line {\
background-color: #151926\
}\
.ace-iris-night .ace_marker-layer .ace_selected-word {\
border: 1px solid #373B41\
}\
.ace-iris-night .ace_invisible {\
color: #4B4E55\
}\
.ace-iris-night .ace_keyword,\
.ace-iris-night .ace_meta,\
.ace-iris-night .ace_storage,\
.ace-iris-night .ace_storage.ace_type,\
.ace-iris-night .ace_support.ace_type {\
color: #B294BB\
}\
.ace-iris-night .ace_keyword.ace_operator {\
color: #8ABEB7\
}\
.ace-iris-night .ace_constant.ace_character,\
.ace-iris-night .ace_constant.ace_language,\
.ace-iris-night .ace_constant.ace_numeric,\
.ace-iris-night .ace_keyword.ace_other.ace_unit,\
.ace-iris-night .ace_support.ace_constant,\
.ace-iris-night .ace_variable.ace_parameter {\
color: #DE935F\
}\
.ace-iris-night .ace_constant.ace_other {\
color: #CED1CF\
}\
.ace-iris-night .ace_invalid {\
color: #CED2CF;\
background-color: #DF5F5F\
}\
.ace-iris-night .ace_invalid.ace_deprecated {\
color: #CED2CF;\
background-color: #B798BF\
}\
.ace-iris-night .ace_fold {\
background-color: #81A2BE;\
border-color: #C5C8C6\
}\
.ace-iris-night .ace_entity.ace_name.ace_function,\
.ace-iris-night .ace_support.ace_function,\
.ace-iris-night .ace_variable {\
color: #81A2BE\
}\
.ace-iris-night .ace_support.ace_class,\
.ace-iris-night .ace_support.ace_type {\
color: #F0C674\
}\
.ace-iris-night .ace_heading,\
.ace-iris-night .ace_markup.ace_heading,\
.ace-iris-night .ace_string {\
color: #B5BD68\
}\
.ace-iris-night .ace_entity.ace_name.ace_tag,\
.ace-iris-night .ace_entity.ace_other.ace_attribute-name,\
.ace-iris-night .ace_meta.ace_tag,\
.ace-iris-night .ace_string.ace_regexp,\
.ace-iris-night .ace_variable {\
color: #CC6666\
}\
.ace-iris-night .ace_comment {\
color: #969896\
}\
.ace-iris-night .ace_indent-guide {\
background: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAACCAYAAACZgbYnAAAAEklEQVQImWNgYGBgYHB3d/8PAAOIAdULw8qMAAAAAElFTkSuQmCC) right repeat-y\
}";

var dom = require("../lib/dom");
dom.importCssString(exports.cssText, exports.cssClass);
});                (function() {
                    ace.require(["ace/theme/iris_night"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
