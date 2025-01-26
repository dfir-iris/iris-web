function update_settings() {
    var data_sent = $('form#form_srv_settings').serializeObject();
    data_sent['prevent_post_mod_repush'] = $('#prevent_post_mod_repush').is(":checked");
    data_sent['prevent_post_objects_repush'] = $('#prevent_post_objects_repush').is(":checked");
    data_sent['password_policy_upper_case'] = $('#password_policy_upper_case').is(":checked");
    data_sent['password_policy_lower_case'] = $('#password_policy_lower_case').is(":checked");
    data_sent['password_policy_digit'] = $('#password_policy_digit').is(":checked");
    data_sent['enforce_mfa'] = $('#enforce_mfa').is(":checked");
    data_sent['password_policy_min_length'] = $('#password_policy_min_length').val().toString();

    post_request_api('/manage/settings/update', JSON.stringify(data_sent), true)
    .done((data) => {
        notify_auto_api(data);
    });
}


function init_db_backup() {

    get_request_api('/manage/server/backups/make-db')
    .done((data) => {
            msg = ""
            for (idx in data.data) {
                msg += data.data[idx] + '\n';
            }
            swal("Done",
             msg,
            {
                icon: "success"
            });
    })
    .fail((error) => {
        for (idx in error.responseJSON.data) {
            msg += data.data[idx] + '\n';
        }

        swal("Error",
         msg,
        {
            icon: "error"
        });
    });
}