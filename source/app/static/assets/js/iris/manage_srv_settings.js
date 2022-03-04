function update_settings() {
    var data_sent = $('form#form_srv_settings').serializeObject();
    data_sent['prevent_post_mod_repush'] = $('#prevent_post_mod_repush').is(":checked");

    $.ajax({
        url: '/manage/settings/update' + case_param(),
        type: "POST",
        data: JSON.stringify(data_sent),
        dataType: "json",
        contentType: "application/json;charset=UTF-8",
        send: function () {$('#save_srv_settings').text("Submitting settings.. ");},
        success: function (data) {
            if (data.status == 'success') {
                notify_success('Settings saved');
            } else {
                notify_error(data.message);
            }
        },
        error: function (error) {
            data = error.responseJSON;
            notify_error(data.message);
            propagate_form_api_errors(data.data);
            $('#save_srv_settings').text("Retry");
        }
    });
}

