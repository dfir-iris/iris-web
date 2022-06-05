function update_settings() {
    var data_sent = $('form#form_srv_settings').serializeObject();
    data_sent['prevent_post_mod_repush'] = $('#prevent_post_mod_repush').is(":checked");
    data_sent['enable_updates_check'] = $('#enable_updates_check').is(":checked");
    data_sent['prevent_post_mod_repush'] = $('#prevent_post_mod_repush').is(":checked");
    data_sent['password_policy_upper_case'] = $('#password_policy_upper_case').is(":checked");
    data_sent['password_policy_lower_case'] = $('#password_policy_lower_case').is(":checked");
    data_sent['password_policy_digit'] = $('#password_policy_digit').is(":checked");

    post_request_api('/manage/settings/update', JSON.stringify(data_sent), true)
    .done((data) => {
        notify_auto_api(data);
    });
}

function unescapeHTML( text ) {
    return text.replace( /&amp;/g, "&" )
               .replace( /&lt;/g, "<" )
               .replace( /&gt;/g, ">" )
               .replace( /&quot;/g, "\"" )
               .replace( /&#39;/g, "'" )
               .replace( /\n/g, "\n\n");
  }


function check_updates() {
    $('#modal_updates').modal({ show: true });
    $('#modal_updates_content').load(
        '/manage/server/check-updates/modal' + case_param(),
        function (response, status, xhr) {
            if (status !== "success") {
                 ajax_notify_error(xhr, '/manage/server/check-updates/modal');
                 document.getElementById('updates_content_md').innerHTML = "Unable to check for updates. Server side error.";
                 return false;
            }
            var conv = new showdown.Converter();
            var txt = document.getElementById('updates_content_md').innerHTML;

            document.getElementById('updates_content_md').innerHTML = conv.makeHtml(txt);
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