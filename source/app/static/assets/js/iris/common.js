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
        icon: 'flaticon-error',
        title: 'Error',
        message: message
    }, {
        type: 'danger',
        placement: {
            from: 'top',
            align: 'right'
        },
        time: 4000,
    });
}

function notify_success(message) {
    $.notify({
        icon: 'flaticon-hands',
        title: 'Done',
        message: message
    }, {
        type: 'success',
        placement: {
            from: 'bottom',
            align: 'right'
        },
        time: 2000,
    });
}

$('#user_context').selectpicker()

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


$(function () {
    var current = location.pathname;
    $('#l_nav_tab .nav-item').each(function () {
        var $this = $(this);
        var child = $this.children();
        // if the current path is like this link, make it active
        if (child.attr('href').startsWith(current)) {
            $this.addClass('active');
            return;
        }
    })
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

function add_rfile() {
    var data = $('form#form_add_receivedfile').serializeObject();
    data['csrf_token'] = $('#csrf_token').val();
    $.ajax({
        url: '/case/evidences/add' + case_param(),
        type: "POST",
        data: JSON.stringify(data),
        contentType: "application/json;charset=UTF-8",
        dataType: "json",
        success: function (data) {
            jsdata = data;
            if (jsdata.status == "success") {
                if (typeof reload_rfiles != "undefined") { reload_rfiles(); }
                $('#modal_add_receivedfile').modal('hide');
                notify_success("File registered");

            } else {
                notify_error("Unable to register file. " + jsdata.message)
            }
        },
        error: function (error) {
            notify_error(error.responseJSON.message);
            propagate_form_api_errors(error.responseJSON.data);
        }
    });
    return false;
}

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

function get_hash() {
  getMD5(
    document.getElementById("input_autofill").files[0],
    prog => $('#btn_rfile_proc').text("Processing "+ (prog * 100).toFixed(2) + "%")
  ).then(
    res => on_done_hash(res),
    err => console.error(err)
  );
}


function on_done_hash(result) {
    $('#btn_rfile_proc').text('Done processing');
    $('#file_hash').val(result);
    $('#filename').val(document.getElementById("input_autofill").files[0].name);
    $('#file_size').val(document.getElementById("input_autofill").files[0].size);
}


function readChunked(file, chunkCallback, endCallback) {
  var fileSize   = file.size;
  var chunkSize  = 4 * 1024 * 1024; // 4MB
  var offset     = 0;

  var reader = new FileReader();
  reader.onload = function() {
    if (reader.error) {
      endCallback(reader.error || {});
      return;
    }
    offset += reader.result.length;
    // callback for handling read chunk
    // TODO: handle errors
    chunkCallback(reader.result, offset, fileSize);
    if (offset >= fileSize) {
      endCallback(null);
      return;
    }
    readNext();
  };

  reader.onerror = function(err) {
    endCallback(err || {});
  };

  function readNext() {
    var fileSlice = file.slice(offset, offset + chunkSize);
    reader.readAsBinaryString(fileSlice);
  }
  readNext();
}

function getMD5(blob, cbProgress) {
  return new Promise((resolve, reject) => {
    var md5 = CryptoJS.algo.MD5.create();
    readChunked(blob, (chunk, offs, total) => {
      md5.update(CryptoJS.enc.Latin1.parse(chunk));
      if (cbProgress) {
        cbProgress(offs / total);
      }
    }, err => {
      if (err) {
        reject(err);
      } else {
        // TODO: Handle errors
        var hash = md5.finalize();
        var hashHex = hash.toString(CryptoJS.enc.Hex);
        resolve(hashHex);
      }
    });
  });
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

                    entry =	`<li class="feed-item ${api_flag}" title='${title}'>
							<time class="date" datetime="${js_data[index].activity_date}">${js_data[index].activity_date}</time>
							<span class="text">${js_data[index].name} - ${js_data[index].activity_desc}</a></span>
						    </li>`
                    $('#case_activities').append(entry);
                }
            }
    });
}

function update_time() {
    $('#current_date').text((new Date()).toLocaleString().slice(0, 17));
}

$(document).ready(function(){
    notify_redirect();
    update_time();
    setInterval(function() { update_time(); }, 30000);
});
