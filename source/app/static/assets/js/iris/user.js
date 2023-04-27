function renew_api() {
    swal({
        title: "Are you sure?",
        text: "The current key will be revoked and cannot be used anymore",
        icon: "warning",
        buttons: true,
        dangerMode: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Go for it'
    })
        .then((willDelete) => {
            if (willDelete) {
                get_request_api('/user/token/renew')
                .done((data) => {
                    if(notify_auto_api(data)) {
                        location.reload(true);
                    }
                })
            } else {
                swal("Pfew, that was close");
            }
        });
}

function save_user_password() {
    clear_api_error();

    if ( $('#user_password').val() != $('#user_password_v').val()) {
        $('#user_password').addClass('is-invalid');
        $('#user_password').after("<div class='invalid-feedback' id='user_password-invalid-msg'>Password and verification are not the same</div>");
        $('#user_password').show();
        return False;
    }

    var data_sent = $('#form_update_pwd').serializeObject();
    data_sent['user_password'] =  $('#user_password').val();

    post_request_api('update', JSON.stringify(data_sent), true)
    .done((data) => {
        if(notify_auto_api(data)) {
            $('#modal_pwd_user').modal('hide');
        }
    });
}

/* Fetch the details of an user and allow modification */
function update_password(user_id) {
    url = 'update/modal' + case_param();
    $('#modal_pwd_user_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
    });
    $('#modal_pwd_user').modal({ show: true });
}

function refresh_user_permissions() {
    var ori_txt = $('#user_refresh_perms_btn').text();
    $('#user_refresh_perms_btn').text('Refreshing..');
     get_request_api('refresh-permissions')
    .done((data) => {
        notify_auto_api(data);
    }).always(() => {
        $('#user_refresh_perms_btn').text(ori_txt);

    });
}

$('input[type=radio][name=iris-theme]').change(function() {
    if (this.value == 'false') {
        theme = 'light'
    }
    else if (this.value == 'true') {
        theme = 'dark';
    } else {
        return;
    }
    get_request_api('theme/set/'+ theme)
    .done((data) => {
        if (notify_auto_api(data, true)) {
            location.reload(true);
        }
    });
});

$('input[type=radio][name=user-has-deletion-prompt]').change(function() {
    if (this.value == 'false') {
        do_prompt = false;
    }
    else if (this.value == 'true') {
       do_prompt = true;
    } else {
        return;
    }
    get_request_api('deletion-prompt/set/'+ do_prompt)
    .then((data) => {
        if (notify_auto_api(data)) {
            userWhoamiRequest(true);
        }
    });

});