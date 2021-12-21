function renew_api() {
    swal({
        title: "Are you sure?",
        text: "The actual key will be revoked and cannot be used anymore",
        icon: "warning",
        buttons: true,
        dangerMode: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Go for it'
    })
        .then((willDelete) => {
            if (willDelete) {
                $.ajax({
                    url: '/user/token/renew' + case_param(),
                    type: "GET",
                    success: function (data) {
                        if (data.status == 'success') {
                            location.reload(true);
                        } else {
                            swal("Oh no !", data.message, "error");
                        }
                    },
                    error: function (error) {
                        swal("Oh no !", error.responseJSON.message, "error");
                    }
                });
            } else {
                swal("Pfew, that's was close");
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

    $.ajax({
        url: 'update' + case_param(),
        type: "POST",
        data: JSON.stringify(data_sent),
        contentType: "application/json;charset=UTF-8",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                swal("You're set !",
                    "The password has been updated successfully",
                    {
                        icon: "success",
                        timer: 500
                    }
                ).then((value) => {
                    $('#modal_pwd_user').modal('hide');
                });

            } else {
                $('#modal_add_user').text('Save again');
                swal("Oh no !", data.message, "error")
            }
        },
        error: function (error) {
            propagate_form_api_errors(error.responseJSON.data);
        }
    });
}

/* Fetch the details of an user and allow modification */
function update_password(user_id) {
    url = 'update/modal' + case_param();
    $('#modal_pwd_user_content').load(url, function () {});
    $('#modal_pwd_user').modal({ show: true });
}