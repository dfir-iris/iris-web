channel = 'iris_update_status';

function log_error(message) {
    add_update_log(message, true);
}

function log_msg(message) {
    add_update_log(message, false)
}

function add_update_log(message, is_error) {
    html_wrap = `<h4><i class="mt-2 fas fa-check text-success"></i>  `
    if (is_error) {
        html_wrap = `<h4><i class="mt-2 fas fa-times text-danger"></i> `
    }
    $("#updates_log").append(html_wrap + message + '</h4><br/>')

}

function get_caseid() {
    queryString = window.location.search;
    urlParams = new URLSearchParams(queryString);

    return urlParams.get('cid')
}

function case_param() {
    var params = {
        cid: get_caseid
    }
    return '?'+ $.param(params);
}

function initiate_update() {
    //update_socket.emit('update_start_update', { 'channel': channel });
    $.ajax({
        url: '/manage/server/start-update' + case_param(),
        type: "GET",
        dataType: "json",
        beforeSend : function () {
            log_msg('Update order sent. Expecting feedback anytime soon');
        },
        success: function (data) {},
        error: function (data) {
            log_error('Unexpected error starting update');
        }
    });
}

var intervalId = null;
var ios = io('/server-updates');
var update_socket = null;

function ping_check_server_online() {
    try {
        update_socket = ios.connect();
        log_msg('Server is back online');
        clearInterval(intervalId);
         $('#tag_bottom').hide();
         $('#update_return_button').show();
    }
    catch(e) {
        console.log('Server still offline');
    }
}

$(document).ready(function(){

    update_socket = ios.connect();

    update_socket.emit('join-update', { 'channel': channel });

    update_socket.on( "update_status", function(data) {
        add_update_log(data.message, data.is_error)
    }.bind() );

    update_socket.on( "server_has_turned_off", function(data) {
        add_update_log('Server is offline, waiting for connection', data.is_error);
        intervalId = window.setInterval(function(){
          ping_check_server_online();
        }, 1000);
    }.bind() );

    update_socket.on( "update_ping", function(data) {
        log_msg('Server connection verified');
        log_msg('Starting update');
        initiate_update();
    }.bind() );

    update_socket.on('disconnect', function () {
        add_update_log('Server is offline, waiting for connection', data.is_error);
        intervalId = window.setInterval(function(){
          ping_check_server_online();
        }, 1000);
    });

    update_socket.on('update_has_fail', function () {
        $('#tag_bottom').hide();
        $('#update_return_button').show();
    });

    update_socket.emit('update_ping', { 'channel': channel });

});