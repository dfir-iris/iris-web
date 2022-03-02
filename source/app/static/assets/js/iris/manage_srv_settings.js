function update_settings() {
    $.ajax({
        url: 'manage/settings/update',
        type: "POST",
        data: $('#form_srv_settings').serializeArray(),
        dataType: "json",
        send: function () {$('#save_srv_settings').text("Submitting settings.. ");},
        success: function (data) {
            if (data.status == 'success') {
                swal("Done !",
                "Settings saved",
                    {
                        icon: "success",
                        timer: 500
                    }
                )
            }
        },
        error: function (error) {
            data = error.responseJSON;
            $('#save_srv_settings').text("Retry");
        }
    });
}

