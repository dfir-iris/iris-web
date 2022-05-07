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
    $('html, body').animate({
        scrollTop: $("#updates_log_end").offset().top
    }, 50);
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
var current_version = null;
var updated_version = null;
var steps = 0;
var no_resp_time = 0;

function check_server_version() {
    $.ajax({
        url: '/api/versions' + case_param(),
        type: "GET",
        dataType: "json",
        timeout: 1000,
        success: function (data) {
            server_version = data.data.iris_current;
            if (server_version == current_version) {
                add_update_log('Something was wrong - server is still in the same version', true);
                add_update_log('Please check server logs', true);
                clearInterval(intervalId);
                $('#tag_bottom').hide();
                $('#update_return_button').show();
            } else {
                add_update_log('Successfully updated from ' + current_version + ' to ' + server_version, false);
                add_update_log('You can now leave this page', false);
                clearInterval(intervalId);
                $('#tag_bottom').hide();
                $('#update_return_button').show();
            }
        },
        error: function (error) {
            log_error('Something\'s wrong, server is not answering');
            log_error('Please check server logs')
            clearInterval(intervalId);
            $('#tag_bottom').hide();
            $('#update_return_button').show();
        }
    });
}

function ping_check_server_online() {

    $.ajax({
        url: '/api/ping' + case_param(),
        type: "GET",
        dataType: "json",
        timeout: 1000,
        success: function (data) {
            $("#offline_time").hide();
            log_msg('Server is back online');
            clearInterval(intervalId);
            check_server_version();
        },
        error: function (error) {
            no_resp_time += 1;
            if (no_resp_time > 29) {
                log_error('Something\'s wrong, server is not answering');
                log_error('Please check server logs')
                clearInterval(intervalId);
                $('#tag_bottom').hide();
                $('#update_return_button').show();
            }
            $("#offline_time").html('<h4 id="offline_time"><i class="fas fa-clock"></i> Attempt '+ no_resp_time +' / 30</h4><br/>');
            $("#offline_time").show();
        }
    });
}

function start_updates(){
    $('#update_start_btn').hide();
    $('.update_start_txt').hide();
    $('#container-updates').show();
    update_socket.emit('update_get_current_version', { 'channel': channel });
    update_socket.emit('update_ping', { 'channel': channel });
//    index = 0;
//    while(index < 20) {
//        add_update_log('ping');
//        index += 1;
//    }
}


$(document).ready(function(){

    update_socket = ios.connect();

    update_socket.on( "update_status", function(data) {
        add_update_log(data.message, data.is_error)
    }.bind() );

    update_socket.on( "update_ping", function(data) {
        log_msg('Server connection verified');
        log_msg('Starting update');
        initiate_update();
    }.bind() );

    update_socket.on( "server_has_updated", function(data) {
        log_msg('Server reported updates applied. Checking . . .');
        check_server_version();
    }.bind() );

    update_socket.on('disconnect', function () {
        add_update_log('Server is offline, waiting for connection', false);
        intervalId = window.setInterval(function(){
            ping_check_server_online();
        }, 1000);
    });

    update_socket.on('update_current_version', function (data) {
        add_update_log('Server reported version ' + data.version , false);
        if (current_version == null) {
            current_version = data.version;
        }
    });

    update_socket.on('update_has_fail', function () {
        $('#tag_bottom').hide();
        $('#update_return_button').show();
    });

    update_socket.emit('join-update', { 'channel': channel });


});