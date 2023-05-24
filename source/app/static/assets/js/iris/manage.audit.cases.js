


function get_case_audit_page() {
    us_val = $('#cases_audit_select').val();
    if (!us_val) {
        notify_error('I really wanna help you but I still can\'t read your mind');
        return false;
    }

    $('#get_case_audit_btn').text('Auditing case..');
    url = '/manage/access-control/audit/cases/'+ us_val +'/modal' + case_param();
    $('#case_audit_content').load(url, function (response, status, xhr) {
        $('#get_case_audit_btn').text('Audit');
        if (status !== "success") {
             $('#get_case_audit_btn').text('Audit');
             ajax_notify_error(xhr, url);

             return false;
        }

        $.each($.find("table"), function(index, element){
            addFilterFields($(element).attr("id"));
        });

        $('#case_audit_access_table').dataTable({
            order: [[ 1, "asc" ]],
            info: true,
            filter: true,
            processing: true,
            orderCellsTop: true,
            initComplete: function () {
                tableFiltering(this.api(), 'case_audit_access_table');
            }
        });
    });
}

function refresh_cases_list_audit() {
    get_request_api('/manage/cases/list')
    .done((data) => {

        if(notify_auto_api(data, true)) {

            $('#cases_audit_select').selectpicker({
                liveSearch: true,
                title: "Select case to audit",
                style: "btn-outline-white",
                size: 10
            });
            data_select = [];
            for (caseid in data.data) {
                label = `${sanitizeHTML(data.data[caseid].case_name)}`;
                $("#cases_audit_select").append('<option value="'+data.data[caseid].case_id+'">'+label+'</option>');
            }
            $("#cases_audit_select").selectpicker("refresh");
            $("#cases_audit_select").show();

        }
    });
}

$(document).ready(function () {
    refresh_cases_list_audit();
});

