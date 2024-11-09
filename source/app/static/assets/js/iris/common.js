$.fn.serializeObject = function() {
    var o = {};
    var a = this.serializeArray();
    $.each(a, function() {
        if (o[this.name]) {
            if (!o[this.name].push) {
                o[this.name] = [o[this.name]];
            }
            o[this.name].push(this.value || '');
        } else {
            o[this.name] = this.value || '';
        }
    });
    return o;
};


var jdata_menu_options = [];
let current_cid = null;

function clear_api_error() {
   $(".invalid-feedback").hide();
}

function setCookie(name,value,days) {
    var expires = "";
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days*24*60*60*1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "")  + expires + "; path=/";
}

function getCookie(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for(var i=0;i < ca.length;i++) {
        var c = ca[i];
        while (c.charAt(0)==' ') c = c.substring(1,c.length);
        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
    }
    return null;
}
function eraseCookie(name) {
    document.cookie = name +'=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
}

function ellipsis_field( data, cutoff, wordbreak ) {

    data = data.toString();
    let anchor = $('<div>');

    if ( data.length <= cutoff ) {
        anchor.text(data);
        return anchor.prop('outerHTML');
    }

    let shortened = data.substr(0, cutoff-1);

    // Find the last white space character in the string
    if ( wordbreak ) {
        shortened = shortened.replace(/\s([^\s]*)$/, '');
    }

    // Build a new anchor tag with the new target
    anchor.text(shortened + '…');
    anchor.className = 'ellipsis';
    anchor.title = data;

    return anchor.prop('outerHTML');
}

function ret_obj_dt_description(data) {
    let anchor = $('<span>');
    let dataContent = typeof data === 'object' ? JSON.stringify(data) : data;
    anchor.attr('data-toggle', 'popover')
        .attr('data-trigger', 'hover')
        .attr('title', 'Description')
        .attr('data-content', dataContent)
        .attr('href', '#')
        .css('cursor', 'pointer')
        .text(ellipsis_field_raw(data, 64));

    return anchor.prop('outerHTML');
}

function render_date(date, show_ms = false) {
    // Remove the timezone information and the ms
    let date_str = date.replace('T', ' ').replace('Z', '');
    if (!show_ms) {
        date_str = date_str.split('.')[0];
    } else {
        // remove nanoseconds
        date_str = date_str.split('.')[0] + '.' + date_str.split('.')[1].substr(0, 3);
    }

    return date_str;
}

function ellipsis_field_raw( data, cutoff, wordbreak ) {
    if (data === undefined || data === null) {
        return '';
    }

    if (data.length <= cutoff) {
        return data;
    }

    let shortened = data.substr(0, cutoff - 1);

    if (wordbreak) {
        shortened = shortened.replace(/\s([^\s]*)$/, '');
    }

    return shortened + '…';
}

function propagate_form_api_errors(data_error) {

    if (typeof (data_error) === typeof (' ')) {
        notify_error(data_error);
        return;
    }

    for (let e in data_error) {
        if($("#" + e).length !== 0) {
            $("#" + e).addClass('is-invalid');
            errors = ""
            for (n in data_error[e]) {
                    errors += data_error[e][n];
                }
            if($("#" + e + "-invalid-msg").length !== 0) {
                $("#" + e + "-invalid-msg").remove();
            }
            $("#" + e).after("<div class='invalid-feedback' id='" + e + "-invalid-msg'>" + errors +"</div>");
            $("#" + e + "-invalid-msg").show();
        }
        else {
            msg = e + " - ";
            for (n in data_error[e]) {
                    msg += data_error[e][n];
            }
            notify_error(msg);
        }
    }
}

function ajax_notify_error(jqXHR, url) {
    if (jqXHR.status == 403) {
        message = 'Permission denied';
    } else {
        message = `We got error ${jqXHR.status} - ${jqXHR.statusText} requesting ${url}`;
    }
    notify_error(message);
}

function notify_error(message) {
    let p = $('<p>')
    p.text(message);
    let data = "";

    if (typeof (message) === typeof ([])) {
        for (element in message) {
            data += element
        }
    } else {
        data = message;
    }
    p.text(data)
    $.notify({
        icon: 'fas fa-triangle-exclamation',
        message: p.prop('outerHTML'),
        title: 'Error'
    }, {
        type: 'danger',
        placement: {
            from: 'bottom',
            align: 'left'
        },
        z_index: 2000,
        timer: 8000,
        animate: {
            enter: 'animated fadeIn',
            exit: 'animated fadeOut'
        }
    });
}

function get_tag_from_data(data, classes) {
    if (data === undefined || data === null || data.length === 0) {
        return '';
    }
    let tag_anchor = $('<span>');
    tag_anchor.addClass(classes);
    tag_anchor.text(data);
    tag_anchor.html('<i class="fa-solid fa-tag mr-1"></i> ' + tag_anchor.html());

    return tag_anchor.prop('outerHTML');
}

function get_ioc_tag_from_data(data, classes) {
    let tag_anchor = $('<span>');
    tag_anchor.addClass(classes);
    tag_anchor.text(data);
    tag_anchor.html('<i class="fa-solid fa-virus"></i> ' + tag_anchor.html());

    return tag_anchor.prop('outerHTML');
}

function notify_success(message) {
    let p = $('<p>')
    p.text(message);
    $.notify({
        icon: 'fas fa-check',
        message: p.prop('outerHTML')
    }, {
        type: 'success',
        placement: {
            from: 'bottom',
            align: 'left'
        },
        z_index: 2000,
        timer: 2500,
        animate: {
            enter: 'animated fadeIn',
            exit: 'animated fadeOut'
        }
    });
}

function notify_auto_api(data, silent_success, silent_failure) {
    if (data.status === 'success') {
        if (silent_success === undefined || silent_success === false) {
            if (data.message.length === 0) {
                data.message = 'Operation succeeded';
            }
            notify_success(data.message);
        }
        return true;
    } else {
        if (data.message.length === 0) {
            data.message = 'Operation failed';
        }
        if (silent_failure === undefined || silent_failure === false) {
            notify_error(data.message);
        }
        return false;
    }
}

function get_request_api(uri, propagate_api_error, beforeSend_fn, cid) {
    if (cid === undefined ) {
     cid = case_param();
    } else {
     cid = '?cid=' + cid;
    }

    uri = uri + cid;
    return get_raw_request_api(uri, propagate_api_error, beforeSend_fn)
}

function get_raw_request_api(uri, propagate_api_error, beforeSend_fn) {
    return $.ajax({
        url: uri,
        type: 'GET',
        dataType: "json",
        beforeSend: function(jqXHR, settings) {
            if (beforeSend_fn !== undefined && beforeSend_fn !== null) {
                beforeSend_fn(jqXHR, settings);
            }
        },
        error: function(jqXHR) {
            if (propagate_api_error) {
                if(jqXHR.responseJSON && jqXHR.status === 400) {
                    propagate_form_api_errors(jqXHR.responseJSON.data);
                } else {
                    ajax_notify_error(jqXHR, this.url);
                }
            } else {
                if (jqXHR.status !== 400) {
                    if(jqXHR.responseJSON) {
                        notify_error(jqXHR.responseJSON.message);
                    } else {
                        ajax_notify_error(jqXHR, this.url);
                    }
                }
            }
        }
    });
}

function set_page_warning(msg) {
    $('#page_warning').text(msg);
}

function get_request_data_api(uri, data, propagate_api_error, beforeSend_fn) {
    return $.ajax({
        url: uri + case_param(),
        type: 'GET',
        data: data,
        dataType: "json",
        beforeSend: function(jqXHR, settings) {
            if (beforeSend_fn !== undefined) {
                beforeSend_fn(jqXHR, settings);
            }
        },
        error: function(jqXHR) {
            if (propagate_api_error) {
                if(jqXHR.responseJSON && jqXHR.status == 400) {
                    propagate_form_api_errors(jqXHR.responseJSON.data);
                } else {
                    ajax_notify_error(jqXHR, this.url);
                }
            } else {
                if(jqXHR.responseJSON) {
                    notify_error(jqXHR.responseJSON.message);
                } else {
                    ajax_notify_error(jqXHR, this.url);
                }
            }
        }
    });
}

function post_request_api(uri, data, propagate_api_error, beforeSend_fn, cid, onError_fn) {
   if (cid === undefined ) {
     cid = case_param();
   } else {
     cid = '?cid=' + cid;
   }

   if (data === undefined || data === null) {
        data = JSON.stringify({
            'csrf_token': $('#csrf_token').val()
        });
   }

   return $.ajax({
        url: uri + cid,
        type: 'POST',
        data: data,
        dataType: "json",
        contentType: "application/json;charset=UTF-8",
        beforeSend: function(jqXHR, settings) {
            if (typeof beforeSend_fn === 'function') {
                beforeSend_fn(jqXHR, settings);
            }
        },
        error: function(jqXHR) {
            if (propagate_api_error) {
                if(jqXHR.responseJSON && jqXHR.status == 400) {
                    propagate_form_api_errors(jqXHR.responseJSON.data);
                } else {
                    ajax_notify_error(jqXHR, this.url);
                }
            } else {
                if(jqXHR.responseJSON) {
                    notify_error(jqXHR.responseJSON.message);
                } else {
                    ajax_notify_error(jqXHR, this.url);
                }
            }
        }
    });
}

function post_request_data_api(uri, data, propagate_api_error, beforeSend_fn) {
   return $.ajax({
        url: uri + case_param(),
        type: 'POST',
        data: data,
        dataType: "json",
        contentType: false,
        processData: false,
        beforeSend: function(jqXHR, settings) {
            if (beforeSend_fn !== undefined) {
                beforeSend_fn(jqXHR, settings);
            }
        },
        error: function(jqXHR) {
            if (propagate_api_error) {
                if(jqXHR.responseJSON && jqXHR.status == 400) {
                    propagate_form_api_errors(jqXHR.responseJSON.data);
                } else {
                    ajax_notify_error(jqXHR, this.url);
                }
            } else {
                if(jqXHR.responseJSON) {
                    notify_error(jqXHR.responseJSON.message);
                } else {
                    ajax_notify_error(jqXHR, this.url);
                }
            }
        }
    });
}

function updateURLParameter(url, param, paramVal) {
    var TheAnchor = null;
    var newAdditionalURL = "";
    var tempArray = url.split("?");
    var baseURL = tempArray[0];
    var additionalURL = tempArray[1];
    var temp = "";

    if (additionalURL)
    {
        var tmpAnchor = additionalURL.split("#");
        var TheParams = tmpAnchor[0];
            TheAnchor = tmpAnchor[1];
        if(TheAnchor)
            additionalURL = TheParams;

        tempArray = additionalURL.split("&");

        for (var i=0; i<tempArray.length; i++)
        {
            if(tempArray[i].split('=')[0] != param)
            {
                newAdditionalURL += temp + tempArray[i];
                temp = "&";
            }
        }
    }
    else
    {
        var tmpAnchor = baseURL.split("#");
        var TheParams = tmpAnchor[0];
            TheAnchor  = tmpAnchor[1];

        if(TheParams)
            baseURL = TheParams;
    }

    if(TheAnchor)
        paramVal += "#" + TheAnchor;

    var rows_txt = temp + "" + param + "=" + paramVal;
    return baseURL + "?" + newAdditionalURL + rows_txt;
}

function get_caseid() {
    if (current_cid === null) {
        let queryString = window.location.search;
        let urlParams = new URLSearchParams(queryString);

        current_cid = urlParams.get('cid')
    }
    return current_cid
}

function is_redirect() {
    queryString = window.location.search;
    urlParams = new URLSearchParams(queryString);

    return urlParams.get('redirect')
}

function notify_redirect() {
    if (is_redirect()) {
        swal("You've been redirected",
             "The case you attempted to reach wasn't found.\nYou have been redirected to a default case.",
             "info", {button: "OK"}
             ).then((value) => {
                    queryString = window.location.search;
                    urlParams = new URLSearchParams(queryString);
                    urlParams.delete('redirect');
                    history.replaceState(null, null, window.location.pathname + '?' + urlParams.toString());
                });
    }
}

function case_param() {
    var params = {
        cid: get_caseid
    }
    return '?'+ $.param(params);
}

var last_state = null;
var need_check = true;
function update_last_resfresh() {
    need_check = true;
    $('#last_resfresh').text("").removeClass("text-warning");
}

function check_update(url) {
    if (need_check) {
        $.ajax({
            url: url + case_param(),
            type: "GET",
            dataType: "json",
            success: function (data) {
                    if (last_state == null || last_state < data.data.object_state) {
                        $('#last_resfresh').text("Updates available").addClass("text-warning");
                        need_check = false;
                    }
                },
            error: function (data) {
                if (data.status == 404) {
                    swal("Stop everything !",
                    "The case you are working on was deleted",
                    "error",
                    {
                        buttons: {
                            again: {
                                text: "Go to my default case",
                                value: "default"
                            }
                        }
                    }
                    ).then((value) => {
                        switch (value) {
                            case "dash":
                                location.reload();
                                break;

                            default:
                                location.reload();
                        }
                    });
                } else if (data.status == 403) {
                    window.location.replace("/case" + case_param());
                } else if (data.status == 400) {

                } else {
                    notify_error('Connection with server lost');
                }
            }
        });
    }
}

function set_last_state(state){
    if (state != null) {
        last_state = state.object_state;
    }
    update_last_resfresh();
}

function show_loader() {
    $('#loading_msg').show();
    $('#card_main_load').hide();
}

function hide_loader() {
    $('#loading_msg').hide();
    $('#card_main_load').show();
    update_last_resfresh();
}

function list_to_badges(wordlist, style, limit, type) {
    badges = "";
    if (wordlist.length > limit) {
       badges = `<span class="badge badge-${style} ml-2">${wordlist.length} ${type}</span>`;
    }
    else {
        wordlist.forEach(function (item, index) {
            badges += `<span class="badge badge-${style} ml-2">${sanitizeHTML(item)}</span>`;
        });
    }

    return badges;
}

var sanitizeHTML = function (str, options) {
    if (options) {
        return filterXSS(str, options);
    } else {
        // Escape the html by default
        return filterXSS(str);
    }
};


function isWhiteSpace(s) {
  return /^\s+$/.test(s);
}

function exportInnerPng() {
    close_sid_var = document.querySelector(".close-quick-sidebar");
    close_sid_var.click();
    div = document.querySelector(".page-inner");
    html2canvas(div, {
        useCORS: true,
        scale: 3,
        backgroundColor: "#f9fbfd"
        }).then(canvas => {
        downloadURI(canvas.toDataURL(), 'iris'+location.pathname.replace('/', '_') + '.png')
    });
}

function downloadURI(uri, name) {
    var link = document.createElement("a");

    link.download = name;
    link.href = uri;
    document.body.appendChild(link);
    link.click();
    link.remove();
}

function copy_object_link(node_id) {
    link = buildShareLink(node_id);
    navigator.clipboard.writeText(link).then(function() {
          notify_success('Shared link copied');
    }, function(err) {
        notify_error('Can\'t copy link. I printed it in console.');
        console.error('Shared link', err);
    });
}
function capitalizeFirstLetter(string) {
  return string.charAt(0).toUpperCase() + string.slice(1);
}

function copy_object_link_md(data_type, node_id){
    let link = `[<i class="fa-solid fa-tag"></i> ${capitalizeFirstLetter(data_type)} #${node_id}](${buildShareLink(node_id)})`
    navigator.clipboard.writeText(link).then(function() {
        notify_success('MD link copied');
    }, function(err) {
        notify_error('Can\'t copy link. I printed it in console.');
        console.error('Shared link', err);
    });
}

function copy_text_clipboardb(data){
    navigator.clipboard.writeText(fromBinary64(data)).then(function() {
        notify_success('Copied');
    }, function(err) {
        notify_error('Can\'t copy link. I printed it in console.');
        console.error(err);
    });
}

function copy_text_clipboard(data){
    navigator.clipboard.writeText(data).then(function() {
        notify_success('Copied');
    }, function(err) {
        notify_error('Can\'t copy link. I printed it in console.');
        console.error(err);
    });
}

function load_case_activity(){
    get_request_api('/case/activities/list')
    .done((data) => {
        js_data = data.data;
        $('#case_activities').empty();
        for (index in js_data) {

            if (js_data[index].is_from_api) {
                api_flag = 'feed-item-primary';
                title = 'Activity issued from API';
            } else {
                api_flag = 'feed-item-default';
                title = 'Activity issued from GUI';
            }

            entry =	`<li class="feed-item ${api_flag}" title='${sanitizeHTML(title)}'>
                    <time class="date" datetime="${js_data[index].activity_date}">${formatTime(js_data[index].activity_date)}</time>
                    <span class="text">${sanitizeHTML(js_data[index].name)} - ${sanitizeHTML(js_data[index].activity_desc)}</span>
                    </li>`
            $('#case_activities').append(entry);
        }
    });
}

function load_dim_limited_tasks(){
    get_request_api('/dim/tasks/list/100')
    .done((data) => {
        js_data = data.data;
        $('#dim_tasks_feed').empty();
        for (index in js_data) {

            if (js_data[index].state == 'success') {
                api_flag = 'feed-item-success';
                title = 'Task succeeded';
            } else {
                api_flag = 'feed-item-warning';
                title = 'Task pending or failed';
            }

            entry =	`<li class="feed-item ${api_flag}" title='${title}'>
                    <time class="date" datetime="${js_data[index].activity_date}">${js_data[index].date_done}</time>
                    <span class="text" title="${js_data[index].task_id}"><a href="#" onclick='dim_task_status("${js_data[index].task_id}");return false;'>${js_data[index].module}</a> - ${js_data[index].user}</span>
                    </li>`
            $('#dim_tasks_feed').append(entry);
        }
    });
}

function dim_task_status(id) {
    url = '/dim/tasks/status/'+id + case_param();
    $('#info_dim_task_modal_body').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        $('#modal_dim_task_detail').modal({show:true});
    });
}

function init_module_processing_wrap(rows, data_type, out_hook_name) {
    console.log(out_hook_name);
    hook_name = null;
    for (opt in jdata_menu_options) {
        console.log(jdata_menu_options[opt]);
        if (jdata_menu_options[opt].manual_hook_ui_name == out_hook_name) {
            hook_name = jdata_menu_options[opt].hook_name;
            hook_ui_name = jdata_menu_options[opt].manual_hook_ui_name;
            module_name = jdata_menu_options[opt].module_name;
            break
        }
    }
    if (hook_name == null) {
        notify_error('Error: hook not found');
        return false;
    }
    return init_module_processing(rows, hook_name, hook_ui_name, module_name, data_type);
}

function init_module_processing(rows, hook_name, hook_ui_name, module_name, data_type) {
    var data = Object();
    data['hook_name'] = hook_name;
    data['module_name'] = module_name;
    data['hook_ui_name'] = hook_ui_name;
    data['csrf_token'] = $('#csrf_token').val();
    data['type'] = data_type;
    data['targets'] = [];

    type_map = {
        "ioc": "ioc_id",
        "asset": "asset_id",
        "task": "task_id",
        "global_task": "task_id",
        "evidence": "id"
    }

    for (index in rows) {
        if (typeof rows[index] === 'object') {
            data['targets'].push(rows[index][type_map[data_type]]);
        } else {
            data['targets'].push(rows[index]);
        }
    }

    post_request_api("/dim/hooks/call", JSON.stringify(data), true)
    .done(function (data){
        notify_auto_api(data)
    });
}

function load_menu_mod_options_modal(element_id, data_type, anchor) {
    get_request_api('/dim/hooks/options/'+ data_type +'/list')
    .done(function (data){
        if(notify_auto_api(data, true)) {
            if (data.data != null) {
                let jsdata = data.data;
                if (jsdata.length !== 0 && anchor.children().length !== 0){
                    anchor.append('<div class="dropdown-divider"></div>');
                }

                for (option in jsdata) {
                    let opt = jsdata[option];
                    let menu_opt = `<a class="dropdown-item" href="#" onclick='init_module_processing(["${element_id}"], "${opt.hook_name}",`+
                                `"${opt.manual_hook_ui_name}","${opt.module_name}","${data_type}");return false;'><i class="fa fa-arrow-alt-circle-right mr-2"></i> ${opt.manual_hook_ui_name}</a>`
                    anchor.append(menu_opt);
                }

            }
        }
    })
}

function get_row_id(row) {
    let ids_map = ["ioc_id","asset_id","task_id","id"];
    for (let id in ids_map) {
        if (row[ids_map[id]] !== undefined) {
            return row[ids_map[id]];
        }
    }
    return null;
}

function get_row_value(row, column) {
    let ids_map = ["asset_name","ioc_value","filename","id"];
    for (let id in ids_map) {
        if (row[ids_map[id]] !== undefined) {
            return row[ids_map[id]];
        }
    }
    return null;
}

var iClassWhiteList = ['fa-solid fa-tags','fa-solid fa-tag', 'fa-solid fa-bell', 'fa-solid fa-virus-covid text-danger mr-1',
'fa-solid fa-file-shield text-success mr-1', 'fa-regular fa-file mr-1', 'fa-solid fa-lock text-success mr-1']

function get_new_ace_editor(anchor_id, content_anchor, target_anchor, onchange_callback, do_save, readonly, live_preview) {
    var editor = ace.edit(anchor_id);
    if ($("#"+anchor_id).attr("data-theme") != "dark") {
        editor.setTheme("ace/theme/tomorrow");
    } else {
        editor.setTheme("ace/theme/iris_night");
    }
    editor.session.setMode("ace/mode/markdown");
    if (readonly !== undefined) {
        editor.setReadOnly(readonly);
    }
    editor.renderer.setShowGutter(true);
    editor.setOption("showLineNumbers", true);
    editor.setOption("showPrintMargin", false);
    editor.setOption("displayIndentGuides", true);
    editor.setOption("maxLines", "Infinity");
    editor.setOption("minLines", "2");
    editor.setOption("autoScrollEditorIntoView", true);
    editor.session.setUseWrapMode(true);
    editor.setOption("indentedSoftWrap", false);
    editor.renderer.setScrollMargin(8, 5)
    editor.setOption("enableBasicAutocompletion", true);

    if (do_save !== undefined && do_save !== null) {
        editor.commands.addCommand({
            name: 'save',
            bindKey: {win: "Ctrl-S", "mac": "Cmd-S"},
            exec: function(editor) {
                do_save()
            }
        });
    }

    editor.commands.addCommand({
        name: 'bold',
        bindKey: {win: "Ctrl-B", "mac": "Cmd-B"},
        exec: function(editor) {
            editor.insertSnippet('**${1:$SELECTION}**');
        }
    });
    editor.commands.addCommand({
        name: 'italic',
        bindKey: {win: "Ctrl-I", "mac": "Cmd-I"},
        exec: function(editor) {
            editor.insertSnippet('*${1:$SELECTION}*');
        }
    });
    editor.commands.addCommand({
        name: 'head_1',
        bindKey: {win: "Ctrl-Shift-1", "mac": "Cmd-Shift-1"},
        exec: function(editor) {
            editor.insertSnippet('# ${1:$SELECTION}');
        }
    });
    editor.commands.addCommand({
        name: 'head_2',
        bindKey: {win: "Ctrl-Shift-2", "mac": "Cmd-Shift-2"},
        exec: function(editor) {
            editor.insertSnippet('## ${1:$SELECTION}');
        }
    });
    editor.commands.addCommand({
        name: 'head_3',
        bindKey: {win: "Ctrl-Shift-3", "mac": "Cmd-Shift-3"},
        exec: function(editor) {
            editor.insertSnippet('### ${1:$SELECTION}');
        }
    });
    editor.commands.addCommand({
        name: 'head_4',
        bindKey: {win: "Ctrl-Shift-4", "mac": "Cmd-Shift-4"},
        exec: function(editor) {
            editor.insertSnippet('#### ${1:$SELECTION}');
        }
    });

    editor.commands.addCommand({
        name: 'link',
        bindKey: {win: "Ctrl-K", "mac": "Cmd-K"},
        exec: function(editor) {
            editor.insertSnippet('[${1:$SELECTION}](url)');
        }
    });

    editor.commands.addCommand({
        name: 'code',
        bindKey: {win: "Ctrl-`", "mac": "Cmd-`"},
        exec: function(editor) {
            editor.insertSnippet('```${1:$SELECTION}```')
        }
    });

    if (live_preview === undefined || live_preview === true) {
        let textarea = $('#'+content_anchor);
        // Remove any previous event handler
        editor.getSession().off("change");

        editor.getSession().on("change", function () {
            if (onchange_callback !== undefined && onchange_callback !== null) {
                onchange_callback();
            }

            textarea.text(editor.getSession().getValue());
            let target = document.getElementById(target_anchor);
            let converter = get_showdown_convert();
            let html = converter.makeHtml(editor.getSession().getValue());
            target.innerHTML = do_md_filter_xss(html);

        });

        textarea.text(editor.getSession().getValue());
        let target = document.getElementById(target_anchor);
        let converter = get_showdown_convert();
        let html = converter.makeHtml(editor.getSession().getValue());
        target.innerHTML = do_md_filter_xss(html);

    }

    return editor;
}

function createSanitizeExtensionForImg() {
  return [
    {
      type: 'lang',
      regex: /<.*?>/g,
      replace: function (match) {
        if (match.startsWith('<img')) {
          return match.replace(/on\w+="[^"]*"/gi, '');
        }
        return match;
      },
    },
  ];
}


function get_showdown_convert() {
    return new showdown.Converter({
        tables: true,
        parseImgDimensions: true,
        emoji: true,
        smoothLivePreview: true,
        strikethrough: true,
        tasklists: true,
        ghCodeBlocks: true,
        backslashEscapesHTMLTags: true,
        splitAdjacentBlockquotes: true,
        extensions: [createSanitizeExtensionForImg, 'bootstrap-tables']
    });
}

function do_md_filter_xss(html) {
    return filterXSS(html, {
        stripIgnoreTag: false,
        whiteList: {
                i: ['class', "title"],
                a: ['href', 'title', 'target'],
                img: ['src', 'alt', 'title', 'width', 'height'],
                div: ['class'],
                p: [],
                hr: [],
                h1: [], h2: [], h3: [], h4: [], h5: [], h6: [],
                ul: [], ol: [], li: [],
                code: [], pre: [], em: [], strong: [],
                blockquote: [], del: [],
                input: ['type', 'checked', 'disabled', 'class'],
                table: ['class'], thead: [], tbody: [], tr: [], th: [], td: [], br: []
            },

        onTagAttr: function (tag, name, value, isWhiteAttr) {
            if (tag === "i" && name === "class") {
                if (iClassWhiteList.indexOf(value) === -1) {
                    return false;
                } else {
                    return name + '="' + value + '"';
                }
            }
          }
        });
}

const avatarCache = {};

function get_avatar_initials(name, small, onClickFunction, xsmall) {
    let av_size = small ? 'avatar-sm' : 'avatar';
    av_size = xsmall ? 'avatar-xs' : av_size;
    const onClick = onClickFunction ? `onclick="${onClickFunction}"` : '';

    if (avatarCache[name] && avatarCache[name][small ? 'small' : 'large']) {
        return `<div class="avatar ${av_size}" title="${name}" ${onClick}>
            ${avatarCache[name][small ? 'small' : 'large']}
        </div>`;
    }

    // Remove any trailing or leading spaces
    name = name.trim();

    const initial = name.split(' ');
    let snum;

    if (initial.length > 1 && initial[1][0] !== undefined) {
        snum = initial[0][0].charCodeAt(0) + initial[1][0].charCodeAt(0);
    } else {
        snum = initial[0][0].charCodeAt(0);
    }

    const initials = initial.map(i => i[0] ? i[0].toUpperCase(): '').join('');
    const avatarColor = get_avatar_color(snum);

    const avatarHTMLin = `<span class="avatar-title avatar-iris rounded-circle" style="background-color:${avatarColor}; cursor:pointer;">${initials}</span>`
    const avatarHTMLout = `<div class="avatar ${av_size}" title="${name}" ${onClick}>
        ${avatarHTMLin}
    </div>`;

    if (!avatarCache[name]) {
        avatarCache[name] = {};
    }
    avatarCache[name][small ? 'small' : 'large'] = avatarHTMLin;

    return avatarHTMLout;
}

function get_avatar_color(snum) {
    const hue = snum * 137.508 % 360; // Use the golden angle for more distinct colors
    const saturation = 40 + (snum % 20); // Saturation range: 40-60
    const lightness = 55 + (snum % 10); // Lightness range: 70-80

    return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}


function edit_inner_editor(btn_id, container_id, ctrd_id) {
    $('#'+container_id).toggle();
    if ($('#'+container_id).is(':visible')) {
        $('#'+btn_id).show(100);
        $('#'+ctrd_id).removeClass('col-md-12').addClass('col-md-6');
    } else {
        $('#'+btn_id).hide(100);
        $('#'+ctrd_id).removeClass('col-md-6').addClass('col-md-12');
    }
    return false;
}

function get_editor_headers(editor_instance, save, edition_btn) {
    var save_html = `<div class="btn btn-sm btn-light mr-1 " title="CTRL-S" id="last_saved" onclick="${save}( this );"><i class="fa-solid fa-file-circle-check"></i></div>`;
    if (save === undefined || save === null) {
        save_html = '';
    }
    header = `
                ${save_html}
                <div class="btn btn-sm btn-light mr-1 " title="CTRL-B" onclick="${editor_instance}.insertSnippet`+"('**${1:$SELECTION}**');"+`${editor_instance}.focus();"><i class="fa-solid fa-bold"></i></div>
                <div class="btn btn-sm btn-light mr-1" title="CTRL-I" onclick="${editor_instance}.insertSnippet`+"('*${1:$SELECTION}*');"+`${editor_instance}.focus();"><i class="fa-solid fa-italic"></i></div>
                <div class="btn btn-sm btn-light mr-1" title="CTRL-SHIFT-1" onclick="${editor_instance}.insertSnippet`+"('# ${1:$SELECTION}');"+`${editor_instance}.focus();">H1</div>
                <div class="btn btn-sm btn-light mr-1" title="CTRL-SHIFT-2" onclick="${editor_instance}.insertSnippet`+"('## ${1:$SELECTION}')"+`;${editor_instance}.focus();">H2</div>
                <div class="btn btn-sm btn-light mr-1" title="CTRL-SHIFT-3" onclick="${editor_instance}.insertSnippet`+"('### ${1:$SELECTION}');"+`${editor_instance}.focus();">H3</div>
                <div class="btn btn-sm btn-light mr-1" title="CTRL-SHIFT-4" onclick="${editor_instance}.insertSnippet`+"('#### ${1:$SELECTION}');"+`${editor_instance}.focus();">H4</div>
                <div class="btn btn-sm btn-light mr-1" title="CTRL+\`" onclick="${editor_instance}.insertSnippet`+"('```${1:$SELECTION}```');"+`${editor_instance}.focus();"><i class="fa-solid fa-code"></i></div>
                <div class="btn btn-sm btn-light mr-1" title="CTRL-K" onclick="${editor_instance}.insertSnippet`+"('[${1:$SELECTION}](URL)');"+`${editor_instance}.focus();"><i class="fa-solid fa-link"></i></div>
                <div class="btn btn-sm btn-light mr-1" title="Insert table" onclick="${editor_instance}.insertSnippet`+"('|\\t|\\t|\\t|\\n|--|--|--|\\n|\\t|\\t|\\t|\\n|\\t|\\t|\\t|');"+`${editor_instance}.focus();"><i class="fa-solid fa-table"></i></div>
                <div class="btn btn-sm btn-light mr-1" title="Insert bullet list" onclick="${editor_instance}.insertSnippet`+"('\\n- \\n- \\n- ');"+`${editor_instance}.focus();"><i class="fa-solid fa-list"></i></div>
                <div class="btn btn-sm btn-light mr-1" title="Insert numbered list" onclick="${editor_instance}.insertSnippet`+"('\\n1. a  \\n2. b  \\n3. c  ');"+`${editor_instance}.focus();"><i class="fa-solid fa-list-ol"></i></div>
                <div class="btn btn-sm btn-transparent mr-1" title="Help" onclick="get_md_helper_modal();"><i class="fa-solid fa-question-circle"></i></div>

    `
    return header;
}

function goto_case_number() {
    case_id = $('#goto_case_number_input').val();
    if (case_id !== '' && isNaN(case_id) === false) {

        get_request_api('/case/exists', true, null, case_id)
        .done(function (data){
            if(notify_auto_api(data, true)) {
                var url = new window.URL(document.location);
                url.searchParams.set("cid", case_id);
                window.location.href = url.href;
            }
        });

    }
}


function load_menu_mod_options(data_type, table, deletion_fn, additionalOptions = []) {
    var actionOptions = {
        classes: [],
        contextMenu: {
            enabled: true,
            isMulti: true,
            xoffset: -10,
            yoffset: -10,
            headerRenderer: function (rows) {
                if (rows.length > 1) {
                    return rows.length + ' items selected';
                } else {
                    let row = rows[0];
                    return 'Quick action';
                }
            },
        },
        buttonList: {
            enabled: false,
        },
        deselectAfterAction: true,
        items: [],
    };

    let datatype_map = {
        'task': 'tasks',
        'ioc': 'ioc',
        'evidence': 'evidences',
        'note': 'notes',
        'asset': 'assets',
        'event': 'timeline/events'
    };

    get_request_api("/dim/hooks/options/" + data_type + "/list")
    .done((data) => {
        if (notify_auto_api(data, true)) {
            if (data.data != null) {
                let jsdata = data.data;

                actionOptions.items.push({
                    type: 'option',
                    title: 'Share',
                    multi: false,
                    iconClass: 'fas fa-share',
                    action: function(rows) {
                        let row = rows[0];
                        copy_object_link(get_row_id(row));
                    }
                });

                actionOptions.items.push({
                    type: 'option',
                    title: 'Comment',
                    multi: false,
                    iconClass: 'fas fa-comments',
                    action: function(rows) {
                        let row = rows[0];
                        if (data_type in datatype_map) {
                            comment_element(get_row_id(row), datatype_map[data_type]);
                        }
                    }
                });

                actionOptions.items.push({
                    type: 'option',
                    title: 'Markdown Link',
                    multi: false,
                    iconClass: 'fa-brands fa-markdown',
                    action: function(rows) {
                        let row = rows[0];
                        copy_object_link_md(data_type, get_row_id(row));
                    }
                });

                actionOptions.items.push({
                    type: 'option',
                    title: 'Copy',
                    multi: false,
                    iconClass: 'fa-regular fa-copy',
                    action: function(rows) {
                        let row = rows[0];
                        copy_text_clipboard(get_row_value(row));
                    }
                });

                additionalOptions.forEach(option => {
                    actionOptions.items.push(option);
                });

                actionOptions.items.push({
                    type: 'divider'
                });

                for (let option in jsdata) {
                    let opt = jsdata[option];

                    actionOptions.items.push({
                        type: 'option',
                        title: opt.manual_hook_ui_name,
                        multi: true,
                        multiTitle: opt.manual_hook_ui_name,
                        iconClass: 'fas fa-rocket',
                        contextMenuClasses: ['text-dark'],
                        action: function(rows, de, ke) {
                            init_module_processing_wrap(rows, data_type, de[0].outerText);
                        },
                    });
                }

                if (deletion_fn !== undefined) {
                    actionOptions.items.push({
                        type: 'divider',
                    });

                    actionOptions.items.push({
                        type: 'option',
                        title: 'Delete',
                        multi: false,
                        iconClass: 'fas fa-trash',
                        contextMenuClasses: ['text-danger'],
                        action: function(rows) {
                            let row = rows[0];
                            deletion_fn(get_row_id(row));
                        }
                    });
                }

                let tableActions = table.contextualActions(actionOptions);
                tableActions.update();
            }
        }
    });
}



function get_custom_attributes_fields() {
    values = Object();
    has_error = [];
    $("input[id^='inpstd_']").each(function (i, el) {
        tab = $(el).attr('data-ref-tab');
        field = $(el).attr('data-attr-for');
        if (!(tab in values)) { values[tab] = {} };

        values[tab][field] = $(el).val();
        if ($(el).prop('required') && !values[tab][field]) {
            $(el).parent().addClass('has-error');
            has_error.push(field);
        } else {
             $(el).parent().removeClass('has-error');
        }
    })
    $("textarea[id^='inpstd_']").each(function (i, el) {
        tab = $(el).attr('data-ref-tab');
        field = $(el).attr('data-attr-for');
        if (!(tab in values)) { values[tab] = {} };
        values[tab][field] = $(el).val();
        if ($(el).prop('required') && !values[tab][field]) {
            $(el).parent().addClass('has-error');
            has_error.push(field);
        } else {
             $(el).parent().removeClass('has-error');
        }
    })
    $("input[id^='inpchk_']").each(function (i, el) {
        tab = $(el).attr('data-ref-tab');
        field = $(el).attr('data-attr-for');
        if (!(tab in values)) { values[tab] = {} };
        values[tab][field] = $(el).is(':checked');
    })
    $("select[id^='inpselect_']").each(function (i, el) {
        tab = $(el).attr('data-ref-tab');
        field = $(el).attr('data-attr-for');
        if (!(tab in values)) { values[tab] = {} };
        values[tab][field] = $(el).val();
        if ($(el).prop('required') && !values[tab][field]) {
            $(el).parent().addClass('has-error');
            has_error.push(field);
        } else {
             $(el).parent().removeClass('has-error');
        }
    })

    if (has_error.length > 0) {
        msg = 'Missing required fields: <br/>';
        for (field in has_error) {
            msg += '  - ' + has_error[field] + '<br/>';
        }
        notify_error(msg);
    }

    return [has_error, values];
}

function update_time() {
    $('#current_date').text((new Date()).toLocaleString());
}

function formatTime(in_, format) {
    if (typeof(in_) === typeof(1)){
        let date = new Date(Math.floor(in_) * 1000);
        return date.toLocaleString(undefined, format);
    } else if (typeof(in_) === typeof('')) {
        let date = new Date(in_);
        return date.toLocaleString(undefined, format);
    }
}

function download_file(filename, contentType, data) {
    var element = document.createElement('a');
    element.setAttribute('href', 'data:' + contentType + ';charset=utf-8,' + encodeURIComponent(data));
    element.setAttribute('download', filename);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
}

function toggle_focus_mode() {
    class_a = "bg-focus-gradient"
    $(".modal-case-focus").each(function (i, el)  {
        if ($(el).hasClass( class_a )) {
            $(el).removeClass(class_a, 1000);
        } else {
            $(el).addClass(class_a, 1000);
        }
    });
}

function modal_maximize() {
    id = $('#minimized_modal_box').data('target-id');
    $("#" + id).modal("show");
    $("#minimized_modal_box").hide();
}

function modal_minimized(id, title) {
    $("#minimized_modal_title").text(title);
    $('#minimized_modal_box').data('target-id',id);
    $("#minimized_modal_box").show();
    $("#" + id).modal("hide");
}

function hide_minimized_modal_box() {
    $("#minimized_modal_box").hide();
    $("#minimized_modal_title").text('');
    $('#minimized_modal_box').data('target-id','');
}

function hide_table_search_input(columns) {
    for (i=0; i<columns.length; i++) {
      if (columns[i]) {
        $('.filters th:eq(' + i + ')' ).show();
      } else {
        $('.filters th:eq(' + i + ')' ).hide();
      }
    }
  }

function load_add_case() {
    // Dynamically load the modal
    $('#modal_add_case_content').load('/manage/cases/add/modal', function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, '/case/add');
             return false;
        }
        $('#case_customer').selectpicker({
            liveSearch: true,
            title: "Select customer *",
            style: "btn-outline-white",
            size: 8
        });
        $('#case_template_id').selectpicker({
            liveSearch: true,
            title: "Select case template",
            style: "btn-outline-white",
            size: 8
        });
        $('#case_template_id').prepend(new Option('', ''));
        $('#classification_id').selectpicker({
            liveSearch: true,
            title: "Select classification",
            style: "btn-outline-white",
            size: 8
        });
        $('#classification_id').prepend(new Option('', ''));

        $('#modal_add_case').modal({show:true});
    });
}

/* Submit event handler for new case */
function submit_new_case() {

    let data_sent = $('form#form_new_case').serializeObject();
    let ret = get_custom_attributes_fields();
    let has_error = ret[0].length > 0;
    let attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;

    send_add_case(data_sent);

    return false;
}

function set_suggest_tags(anchor_id) {
    $(`#${anchor_id}`).amsifySuggestags({
        suggestionsAction : {
            url : '/manage/tags/suggest',
            method: 'GET',
            timeout: -1,
            minChars: 2,
            minChange: -1,
            delay: 100,
            type: 'GET',
            dataType: null
        }
    });
}

function send_add_case(data_sent) {

    post_request_api('/manage/cases/add', JSON.stringify(data_sent), true, function () {
        $('#submit_new_case_btn').text('Checking data..')
            .attr("disabled", true)
            .removeClass('bt-outline-success')
            .addClass('btn-success', 'text-dark');
    })
    .done((data) => {
        if (notify_auto_api(data, true)) {
            let case_id = data.data.case_id;
            swal("That's done !",
                "Case has been successfully created",
                "success",
                {
                    buttons: {
                        dash: {
                            text: "Go to dashboard",
                            value: "dash",
                            color: '#d33'
                        },
                        go_case: {
                            text: "Switch to newly created case",
                            value: "go_case"
                        }
                    }
                }
            ).then((value) => {
                switch (value) {

                    case "dash":
                        window.location.replace("/dashboard" + case_param());
                        break;

                    case 'go_case':
                        window.location.replace("/case?cid=" + case_id);

                    default:
                        window.location.replace("/case?cid=" + case_id);
                }
            });
        }
    })
    .always(() => {
        $('#submit_new_case_btn')
        .attr("disabled", false)
        .addClass('bt-outline-success')
        .removeClass('btn-success', 'text-dark');
    })
    .fail(() => {
        $('#submit_new_case_btn').text('Save');
    })

}

function load_context_switcher() {

    var options = {
            ajax: {
            url: '/context/search-cases'+ case_param(),
            type: 'GET',
            dataType: 'json'
        },
        locale: {
                emptyTitle: 'Select and Begin Typing',
                statusInitialized: '',
        },
        minLength: 0,
        clearOnEmpty: false,
        emptyRequest: true,
        preprocessData: function (data) {
            return context_data_parser(data);
        },
        preserveSelected: false
    };


    get_request_api('/context/search-cases')
    .done((data) => {
        context_data_parser(data);
        $('#user_context').ajaxSelectPicker(options);
    });
}

function context_data_parser(data, fire_modal = true) {
    if(notify_auto_api(data, true)) {
        $('#user_context').empty();

        $('#user_context').append('<optgroup label="Open" id="switch_case_opened_opt"></optgroup>');
        $('#user_context').append('<optgroup label="Closed" id="switch_case_closed_opt"></optgroup>');
        ocs = data.data;
        ret_data = [];
        for (index in ocs) {
            case_name = sanitizeHTML(ocs[index].name);
            cs_name = sanitizeHTML(ocs[index].customer_name);
            ret_data.push({
                        'value': ocs[index].case_id,
                        'text': `${case_name} (${cs_name}) ${ocs[index].access}`
                    });
            if (ocs[index].close_date != null) {
                $('#switch_case_closed_opt').append(`<option value="${ocs[index].case_id}">${case_name} (${cs_name}) ${ocs[index].access}</option>`);
            } else {
                $('#switch_case_opened_opt').append(`<option value="${ocs[index].case_id}">${case_name} (${cs_name}) ${ocs[index].access}</option>`)
            }
        }

        if (fire_modal) {
            $('#modal_switch_context').modal("show");
        }

        $('#user_context').selectpicker('refresh');
        $('#user_context').selectpicker('val', get_caseid());
        return ret_data;

    }
}

function focus_on_input_chg_case(){
    $('#goto_case_number_input').focus();
    $('#goto_case_number_input').keydown(function(event) {
        if (event.keyCode == 13) {
             goto_case_number();
             return false;
        }
  });
}

function get_md_helper_modal() {
    $('#modal_md_helper').load('/case/md-helper?cid=' + get_caseid(), function (response, status, xhr) {
         if (status !== "success") {
             ajax_notify_error(xhr, '/case/md-helper?cid=' + get_caseid());
             return false;
            }
         $('#shortcutModal').modal("show");
    });
}

function split_bool(split_str) {
    and_split = split_str.split(' AND ');

    if (and_split[0]) {
      return and_split[0];
    }

    return null;
}

function random_filename(length) {
    var filename           = '';
    var characters       = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    var char_length = characters.length;
    for ( var i = 0; i < length; i++ ) {
      filename += characters.charAt(Math.random() * 1000 % char_length);
   }
   return filename;
}

function createPagination(currentPage, totalPages, per_page, callback, paginationContainersNodes) {
  const maxPagesToShow = 5;
  const paginationContainers = $(paginationContainersNodes);

  if (totalPages === 1 || totalPages === 0) {
    paginationContainers.html('');
    return;
  }

  paginationContainers.each(function() {
    const paginationContainer = $(this);
    paginationContainer.html('');

    const startPage = Math.max(1, currentPage - Math.floor(maxPagesToShow / 2));
    const endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);

    // Add First page button
      if (totalPages > maxPagesToShow) {
          if (currentPage !== 1 && maxPagesToShow / 2 + 1 < currentPage) {
              const firstItem = $('<li>', {class: 'page-item'}).appendTo(paginationContainer);
              $('<a>', {
                  href: `javascript:${callback}(1, ${per_page},{}, true)`,
                  text: 'First page',
                  class: 'page-link',
              }).appendTo(firstItem);
          }
      }

    // Add Previous button
    if (currentPage !== 1) {
        const prevItem = $('<li>', { class: 'page-item' }).appendTo(paginationContainer);
        $('<a>', {
          href: `javascript:${callback}(${Math.max(1, currentPage - 1)}, ${per_page},{}, true)`,
          text: 'Previous',
          class: 'page-link',
        }).appendTo(prevItem);
    }

    // Add page numbers
    for (let i = startPage; i <= endPage; i++) {
      const pageItem = $('<li>', { class: 'page-item' }).appendTo(paginationContainer);
      if (i === currentPage) {
        pageItem.addClass('active');
      }
      $('<a>', {
        href: `javascript:${callback}(${i}, ${per_page},{}, true)`,
        text: i,
        class: 'page-link',
      }).appendTo(pageItem);
    }

    // Add Next button

    if (currentPage !== totalPages) {
        const nextItem = $('<li>', { class: 'page-item' }).appendTo(paginationContainer);
        $('<a>', {
          href: `javascript:${callback}(${Math.min(totalPages, currentPage + 1)}, ${per_page},{}, true)`,
          text: 'Next',
          class: 'page-link',
        }).appendTo(nextItem);
    }

   if (totalPages > maxPagesToShow) {
       if (currentPage !== totalPages) {
            const lastItem = $('<li>', {class: 'page-item'}).appendTo(paginationContainer);
            $('<a>', {
               href: `javascript:${callback}(${totalPages}, ${per_page},{}, true)`,
               text: 'Last page',
               class: 'page-link',
           }).appendTo(lastItem);
       }
   }
  });
}

let userWhoami = JSON.parse(sessionStorage.getItem('userWhoami'));

function userWhoamiRequest(force = false) {
  if (!userWhoami || force) {
    get_request_api('/user/whoami')
      .done((data) => {
        if (notify_auto_api(data, true)) {
            userWhoami = data.data;
          sessionStorage.setItem('userWhoami', JSON.stringify(userWhoami));
        }
      });
  }
}

$('.toggle-sidebar').on('click', function() {
    if ($('.wrapper').hasClass('sidebar_minimize')) {
        $('.wrapper').removeClass('sidebar_minimize');
        get_request_api('/user/mini-sidebar/set/false')
            .then((data) => {
                notify_auto_api(data, true);
            });
    } else {
        $('.wrapper').addClass('sidebar_minimize');
        get_request_api('/user/mini-sidebar/set/true')
            .then((data) => {
                notify_auto_api(data, true);
            });
    }
});

function do_deletion_prompt(message, force_prompt=false) {
    if (userWhoami.has_deletion_confirmation || force_prompt) {
            return new Promise((resolve, reject) => {
                swal({
                    title: "Are you sure?",
                    text: message,
                    icon: "warning",
                    buttons: {
                        cancel: {
                            text: "Cancel",
                            value: false,
                            visible: true,
                            closeModal: true
                        },
                        confirm: {
                           text: "Confirm",
                           value: true
                        }
                    },
                    dangerMode: true
                })
                .then((willDelete) => {
                    resolve(willDelete);
                })
                .catch((error) => {
                    reject(error);
                });
            });
    } else {
        return new Promise((resolve, reject) => {
            resolve(true);
        });
    }
}

function escapeHtml(text) {
    let parser = new DOMParser();
    let escapedDoc = parser.parseFromString(text, 'text/html');
    return escapedDoc.documentElement.textContent;
}

function toBinary64(string) {
  const codeUnits = new Uint16Array(string.length);
  for (let i = 0; i < codeUnits.length; i++) {
    codeUnits[i] = string.charCodeAt(i);
  }
  return btoa(String.fromCharCode(...new Uint8Array(codeUnits.buffer)));
}

function fromBinary64(encoded) {
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return String.fromCharCode(...new Uint16Array(bytes.buffer));
}

$(document).ready(function(){
    notify_redirect();
    update_time();
    setInterval(function() { update_time(); }, 30000);

    $(function () {
        var current = location.pathname;
        btt = current.split('/')[1];

        if (btt !== 'manage') {
            btt = btt.split('?')[0];
        } else {
            csp = current.split('?')[0].split('/')
            if (csp.length >= 3) {
                csp = csp.splice(0, 3);
            }
            btt = csp.join('/');
        }

        $('#l_nav_tab .nav-item').each(function (k, al) {
            href = $(al).children().attr('href');
            try {
                if (href == "#advanced-nav") {
                    $('#advanced-nav .nav-subitem').each(function (i, el) {
                        ktt = $(el).children().attr('href').split('?')[0];
                        if (ktt === btt) {
                            $(el).addClass('active');
                            $(al).addClass('active');
                            $(al).children().attr('aria-expanded', true);
                            $('#advanced-nav').show();
                            return false;
                        }
                    });
                } else if (href.startsWith(btt)){
                    $(this).addClass('active');
                    return false;
                }else{
                    att = "";
                    att = href.split('/')[1].split('?')[0];
                }
            } catch {att=""}
            if (att === btt) {
                $(al).addClass('active');
                return false;
            }
        })
    })

    $('#submit_set_context').click(function () {
    var data_sent = new Object();
    data_sent.ctx = $('#user_context').val();
    data_sent.ctx_h = $("#user_context option:selected").text();
    post_request_api('/context/set?cid=' + data_sent.ctx, data_sent)
    .done((data) => {
            if(notify_auto_api(data, true)) {
                $('#modal_switch_context').modal('hide');
                swal({
                    title: 'Context changed successfully',
                    text: 'Reloading...',
                    icon: 'success',
                    timer: 500,
                    buttons: false,
                })
                .then(() => {
                    var newURL = updateURLParameter(window.location.href, 'cid', data_sent.ctx);
                    window.history.replaceState('', '', newURL);
                    location.reload();
                })
            }
        });
    });

    $(".rotate").click(function () {
        $(this).toggleClass("down");
    });

    $(function () {
        $('[data-toggle="popover"]').popover({
            trigger: 'focus',
            placement: 'auto',
            container: 'body',
            html: true
        });
    });

    $('.modal-dialog').draggable({
        handle: ".modal-header"
    });

    $('#form_add_tasklog').submit(function () {
        event.preventDefault();
        event.stopImmediatePropagation();
        var data = $('form#form_add_tasklog').serializeObject();
        data['csrf_token'] = $('#csrf_token').val();

        post_request_api('/case/tasklog/add', JSON.stringify(data), true)
        .done(function (data){
            if(notify_auto_api(data)){
                $('#modal_add_tasklog').modal('hide');
            }
        });
        return false;
    });

    var sh_ext = showdown.extension('bootstrap-tables', function () {
      return [{
        type: "output",
        filter: function (html, converter, options) {
            let parser = new DOMParser();

            html = '<div id="fsjpowefjdwe">' + html + '</div>';

            let doc = parser.parseFromString(html, 'text/html');

            let tables = doc.getElementsByTagName('table');

            for (let i = 0; i < tables.length; i++) {
                let table = tables[i];

                table.classList.add('table', 'table-striped', 'table-bordered', 'table-hover', 'table-sm');

                let div = doc.createElement('div');
                div.classList.add('table-responsive');

                table.parentNode.insertBefore(div, table);
                div.appendChild(table);
            }

            let serializer = new XMLSerializer();
            let newHtml = serializer.serializeToString(doc);

            let innerHtml = doc.getElementById('fsjpowefjdwe').innerHTML;

            return innerHtml;

        }
          }];
    });

    userWhoamiRequest();
});


