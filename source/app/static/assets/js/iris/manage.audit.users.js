


function get_user_audit_page() {

    us_val = $('#users_audit_select').val();
    if (!us_val) {
        notify_error('I really wanna help you but I still can\'t read your mind');
        return false;
    }

    $('#get_user_audit_btn').text('Auditing user..');
    url = '/manage/access-control/audit/users/'+ us_val +'/modal' + case_param();
    $('#user_audit_content').load(url, function (response, status, xhr) {
        $('#get_user_audit_btn').text('Audit');
        if (status !== "success") {
             $('#get_user_audit_btn').text('Audit');
             ajax_notify_error(xhr, url);
             return false;
        }

        $.each($.find("table"), function(index, element){
            addFilterFields($(element).attr("id"));
        });

        $('#user_audit_access_table').dataTable({
            order: [[ 1, "asc" ]],
            info: true,
            filter: true,
            processing: true,
            orderCellsTop: true,
            initComplete: function () {
                tableFiltering(this.api(), 'user_audit_access_table');
            }
        });

        $('#user_audit_permissions_table').dataTable({
            order: [[ 1, "asc" ]],
            info: true,
            filter: true,
            processing: true,
            orderCellsTop: true,
            initComplete: function () {
                tableFiltering(this.api(), 'user_audit_permissions_table');
            }
        });

    });
}

function refresh_users_list_audit() {
    get_request_api('/manage/users/list')
    .done((data) => {

        if(notify_auto_api(data, true)) {

            $('#users_audit_select').selectpicker({
                liveSearch: true,
                title: "Select user to audit",
                style: "btn-outline-white",
                size: 10
            });
            data_select = [];
            for (user in data.data) {
                label = `${sanitizeHTML(data.data[user].user_login)} (${sanitizeHTML(data.data[user].user_name)} - ${sanitizeHTML(data.data[user].user_email)})`;
                $("#users_audit_select").append('<option value="'+data.data[user].user_id+'">'+label+'</option>');
            }
            $("#users_audit_select").selectpicker("refresh");
            $("#users_audit_select").show();

        }
    });
}

$(document).ready(function () {
    refresh_users_list_audit();
});

