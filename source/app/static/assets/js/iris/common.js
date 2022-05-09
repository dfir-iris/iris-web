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


function propagate_form_api_errors(data_error) {
    for (e in data_error) {
        if($("#" + e).length != 0) {
            $("#" + e).addClass('is-invalid');
            errors = ""
            for (n in data_error[e]) {
                    errors += data_error[e][n];
                }
            if($("#" + e + "-invalid-msg").length != 0) {
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

function ajax_notify_error(jqXHR, textStatus, errorThrown) {
    message = `<b>We got error ${jqXHR.status}</b><br/>${textStatus} - ${errorThrown}`;
    notify_error(message);
}

function notify_error(message) {

    data = "";
    if (typeof (message) == typeof ([])) {
        for (element in message) {
            data += element
        }
    } else {
        data = message;
    }
    $.notify({
        icon: 'fas fa-times',
        title: 'Error',
        message: data
    }, {
        type: 'danger',
        placement: {
            from: 'top',
            align: 'right'
        },
        time: 8000,
        z_index: 2000,
        animate: {
            enter: 'animate__animated animate__fadeIn',
            exit: 'animate__animated animate__fadeOut'
        }
    });
}

function notify_success(message) {
    $.notify({
        icon: 'fas fa-check',
        title: 'Done',
        message: message,
    }, {
        type: 'success',
        placement: {
            from: 'bottom',
            align: 'right'
        },
        z_index: 2000,
        time: 2000,
        animate: {
                    enter: 'animate__animated animate__fadeIn',
                    exit: 'animate__animated animate__fadeOut'
        }
    });
}

function get_request_wrapper(uri, success_fn) {
    request_wrapper(uri, 'GET', success_fn);
}

function request_wrapper(uri, method, success_fn) {
    $.ajax({
        url: uri + case_param(),
        type: method,
        dataType: "json",
        success: function(data) { success_fn(data); },
        error: function(jqXHR, textStatus, errorThrown) {
            ajax_notify_error(jqXHR, textStatus, errorThrown);
        }
    });
}

function updateURLParameter(url, param, paramVal)
{
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


$('#submit_set_context').click(function () {
    var data_sent = new Object();
    data_sent.ctx = $('#user_context').val();
    data_sent.ctx_h = $("#user_context option:selected").text();
    $.ajax({
        url: '/context/set?cid=' + data_sent.ctx,
        type: "POST",
        data: data_sent,
        dataType: "json",
        success: function (data) {
            jsdata = data;
            if (jsdata.status == "success") {
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
            } else {
                swal({
                    title: 'Ooops',
                    text: jsdata.message,
                    icon: 'error',
                    buttons: true,
                })
            }
        },
        error: function (error) {
            notify_error(error);
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
})

function get_caseid() {
    queryString = window.location.search;
    urlParams = new URLSearchParams(queryString);

    return urlParams.get('cid')
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
                    window.location.search = urlParams;
                });
    }
}

function case_param() {
    var params = {
        cid: get_caseid
    }
    return '?'+ $.param(params);
}

$('#form_add_tasklog').submit(function () {
    event.preventDefault();
    event.stopImmediatePropagation();
    var data = $('form#form_add_tasklog').serializeObject();
    data['csrf_token'] = $('#csrf_token').val();
    $.ajax({
        url: '/case/tasklog/add' + case_param(),
        type: "POST",
        data: JSON.stringify(data),
        contentType: "application/json;charset=UTF-8",
        dataType: "json",
        success: function (data) {
            jsdata = data;
            if (jsdata.status == "success") {
                $('#modal_add_tasklog').modal('hide');
                notify_success("Task log registered");
            } else {
                notify_error("Unable to add task log. " + jsdata.message)
            }
        },
        error: function (error) {
            notify_error(error.responseJSON.message);
            propagate_form_api_errors(error.responseJSON.data);
        }
    });
    return false;
});


var last_state = null;
var need_check = true;
function update_last_resfresh() {
    var dt = new Date();
    var time = ('0'+dt.getHours()).slice(-2) + ":" +  ('0'+dt.getMinutes()).slice(-2) + ":" + ('0'+dt.getSeconds()).slice(-2);
    need_check = true;
    $('#last_resfresh').text("Last refresh "+ time).removeClass("text-warning");
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

var sanitizeHTML = function (str) {
    if (typeof str === 'string') {
        return str.replace(/[^\w. ]/gi, function (c) {
            return '&#' + c.charCodeAt(0) + ';';
        });
    } else if (str == null) {
        return '';
    } else {
        return str;
    }
};

function isWhiteSpace(s) {
  return /^\s+$/.test(s);
}

function exportInnerPng()
{
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
    console.log(link);
    link.click();
    link.remove();
}

function copy_object_link(node_id) {
    link = buildShareLink(node_id);
    navigator.clipboard.writeText(link).then(function() {
          notify_success('Shared link copied')
    }, function(err) {
        console.error('Shared link', err);
    });
}

function load_case_activity(){
    $.ajax({
        url: '/case/activities/list' + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
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
							<time class="date" datetime="${js_data[index].activity_date}">${js_data[index].activity_date}</time>
							<span class="text">${sanitizeHTML(js_data[index].name)} - ${sanitizeHTML(js_data[index].activity_desc)}</span>
						    </li>`
                    $('#case_activities').append(entry);
                }
            }
    });
}


function load_dim_limited_tasks(){
    $.ajax({
        url: '/dim/tasks/list/100' + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
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
            }
    });
}

function dim_task_status(id) {
    url = '/dim/tasks/status/'+id + case_param();
    $('#info_dim_task_modal_body').load(url, function(){
        $('#modal_dim_task_detail').modal({show:true});
    });
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

    $.ajax({
        url: "/dim/hooks/call" + case_param(),
        type: "POST",
        data: JSON.stringify(data),
        dataType: "json",
        contentType: "application/json;charset=UTF-8",
        dataType: 'json',
        success: function (response) {
            if (response.status == 'success') {
                    notify_success('Data sent to module');
            }
        },
        error: function (error) {
            notify_error(error.statusText);
        }
    });
}

function load_menu_mod_options_modal(element_id, data_type, anchor) {

    $.ajax({
        url: '/dim/hooks/options/'+ data_type +'/list' + case_param(),
        type: "GET",
        dataType: 'json',
        success: function (response) {
            if (response.status == 'success') {
                if (response.data != null) {
                    jsdata = response.data;
                    if (jsdata.length != 0) {
                        anchor.append('<div class="dropdown-divider"></div>');
                    }
                    for (option in jsdata) {
                        opt = jsdata[option];
                        menu_opt = `<a class="dropdown-item" href="#" onclick='init_module_processing(["${element_id}"], "${opt.hook_name}",`+
                                    `"${opt.manual_hook_ui_name}","${opt.module_name}","${data_type}");return false;'><i class="fa fa-arrow-alt-circle-right mr-2"></i> ${opt.manual_hook_ui_name}</a>`
                        anchor.append(menu_opt);
                    }
                }
            }
        },
        error: function (error) {
            notify_error(error.statusText);
        }
    });
}

function get_row_id(row) {
    ids_map = ["ioc_id","asset_id","task_id","id"];
    for (id in ids_map) {
        if (row[ids_map[id]] !== undefined) {
            return row[ids_map[id]];
        }
    }
    return null;
}

function load_menu_mod_options(data_type, table) {
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

    $.ajax({
        url: "/dim/hooks/options/"+ data_type +"/list" + case_param(),
        type: "GET",
        dataType: 'json',
        success: function (response) {
            if (response.status == 'success') {
                if (response.data != null) {
                    jsdata = response.data;

                    actionOptions.items.push({
                        type: 'option',
                        title: 'Share',
                        multi: false,
                        iconClass: 'fas fa-share',
                        buttonClasses: ['btn', 'btn-outline-primary'],
                        action: function(rows){
                            row = rows[0];
                            copy_object_link(get_row_id(row));
                        }
                    });
                    actionOptions.items.push({
                        type: 'divider',
                    });
                    for (option in jsdata) {
                        opt = jsdata[option];
                        actionOptions.items.push({
                            type: 'option',
                            title: opt.manual_hook_ui_name,
                            multi: true,
                            multiTitle: opt.manual_hook_ui_name,
                            iconClass: 'fas fa-arrow-alt-circle-right',
                            buttonClasses: ['btn', 'btn-outline-primary'],
                            contextMenuClasses: ['text-dark'],
                            action: function (rows) {
                                init_module_processing(rows, opt.hook_name, opt.manual_hook_ui_name, opt.module_name, data_type);
                            },
                        })
                    }
                    table.contextualActions(actionOptions);
                }
            }
        },
        error: function (error) {
            notify_error(error.statusText);
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
    $('#current_date').text((new Date()).toLocaleString().slice(0, 17));
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

function hide_table_search_input(columns) {
    for (i=0; i<columns.length; i++) {
      if (columns[i]) {
        $('.filters th:eq(' + i + ')' ).show();
      } else {
        $('.filters th:eq(' + i + ')' ).hide();
      }
    }
  }


$('#user_context').selectpicker({liveSearch: true,
    title: "None",
    style: "btn-outline-white"
});
$('#user_context').selectpicker('val', get_caseid());

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
            btt = current.split('?')[0];
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
                            return;
                        }
                    })
                } else if (href.startsWith(btt)){
                    $(this).addClass('active');
                    return;
                }else{
                    att = "";
                    att = href.split('/')[1].split('?')[0];
                }
            } catch {att=""}
            if (att === btt) {
                $(al).addClass('active');
                return;
            }
        })
    })
});
