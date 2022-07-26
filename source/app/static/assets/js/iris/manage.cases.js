/*************************
 *  Case creation section 
 *************************/

/* create the select picker for customer */
$('#case_customer').selectpicker({
    liveSearch: true,
    title: "Select customer *",
    style: "btn-outline-white"
});
$('#case_organisations').selectpicker({
    liveSearch: true,
    title: "Select organisation(s)",
    style: "btn-outline-white"
});

/* Submit event handler for new case */
function submit_new_case() {

    if(!$('form#form_new_case').valid()) {
        return false;
    }

    var data_sent = $('form#form_new_case').serializeObject();
    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;

    if(typeof data_sent['case_organisations'] === 'string') {
        data_sent['case_organisations'] = [data_sent['case_organisations']];
    }

    if (data_sent['case_organisations'] === undefined) {
        swal({
            title: "Attention",
            text: "No organisation selected.\n No one other than you will be able to see and run this case.\n Continue?",
            icon: "warning",
            buttons: true,
            dangerMode: true,
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33',
            buttons: ["Cancel", "Let\'s do that"]
        })
        .then((allAlone) => {
            if (allAlone) {
                send_add_case(data_sent);
            } else {
                notify_success('Case addition canceled');
            }
        });
    }
    else {
        send_add_case(data_sent);
    }
    return false;
};

function send_add_case(data_sent) {

    post_request_api('/manage/cases/add', JSON.stringify(data_sent), true, function () {
        $('#submit_new_case_btn').text('Checking data..')
            .attr("disabled", true)
            .removeClass('bt-outline-success')
            .addClass('btn-success', 'text-dark');
    })
    .done((data) => {
        if (notify_auto_api(data, true)) {
            case_id = data.data.case_id;
            swal("That's done !",
                "Case has been successfully created",
                "success",
                {
                    buttons: {
                        again: {
                            text: "Create a case again",
                            value: "again",
                            dangerMode: true,
                            color: '#d33'
                        },
                        dash: {
                            text: "Go to dashboard",
                            value: "dash",
                            color: '#d33'
                        },
                        go_case: {
                            text: "Switch to newly created case",
                            value: "go_case"
                        }
                    }
                }
            ).then((value) => {
                switch (value) {

                    case "dash":
                        window.location.replace("/dashboard" + case_param());
                        break;

                    case "again":
                        window.location.replace("/manage/cases" + case_param());
                        break;

                    case 'go_case':
                        window.location.replace("/case?cid=" + case_id);

                    default:
                        window.location.replace("/case?cid=" + case_id);
                }
            });
        }
    })
    .always(() => {
        $('#submit_new_case_btn')
        .attr("disabled", false)
        .addClass('bt-outline-success')
        .removeClass('btn-success', 'text-dark');
    })
    .fail(() => {
        $('#submit_new_case_btn').text('Save');
    })

}

 /*************************
 *  Case list section 
 *************************/
/* case table creation */
$('#cases_table').dataTable({
    "ajax": {
        "url": "cases/list" + case_param(),
        "contentType": "application/json",
        "type": "GET",
        "data": function (d) {
            if (d.status == 'success') {
                return JSON.stringify(d.data);
            } else {
                return [];
            }
        }
    },
    "order": [[3, "desc"]],
    "autoWidth": false,
    "columns": [
        {
            "render": function (data, type, row) {
                data = sanitizeHTML(data);
                return '<a href="#" onclick="case_detail(\'' + row['case_id'] + '\');">' + decodeURIComponent(data) + '</a>';
            },
            "data": "case_name"
        },
        {
            "data": "case_description",
            "render": function (data, type, row) {
                if (type === 'display' && data != null) {
                    if (row["case_description"].length > 50){
                        return sanitizeHTML(row["case_description"].slice(0,50)) + " ... " ;
                    }
                    else {
                        return sanitizeHTML(row["case_description"]);
                    }
                }
                return data;
            },
        },
        {
            "data": "client_name",
            "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
        },
        {
            "data": "case_open_date",
            "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
            },
            "type": "date"
        },
        {
            "data": "case_close_date",
            "type": "date",
            "render": function (data, type, row, meta) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
              }
        },
        {
            "data": "case_soc_id",
            "render": function (data, type, row, meta) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
              }
        },
        {
            "data": "opened_by",
            "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
        }
    ]
});

/* Refresh case table function */
function refresh_case_table() {
    $('#cases_table').DataTable().ajax.reload();
    $('#cases_table').DataTable().columns.adjust().draw();
    notify_success("Refreshed");
}

/* Create detail modal function */
function case_detail(id) {
    url = 'cases/details/' + id + case_param();
    $('#info_case_modal_content').load(url, function (response, status, xhr) {

        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#modal_case_detail').modal({ show: true });

    });
}

/* Remove case function */
function remove_case(id) {

    swal({
        title: "Are you sure?",
        text: "You won't be able to revert this !\nAll associated data will be deleted",
        icon: "warning",
        buttons: true,
        dangerMode: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, delete it!'
    })
        .then((willDelete) => {
            if (willDelete) {
                get_request_api('/manage/cases/delete/' + id)
                .done((data) => {
                    if (notify_auto_api(data)) {
                        refresh_case_table();
                        $('#modal_case_detail').modal('hide');
                    }
                });
            } else {
                swal("Pfew, that was close");
            }
        });
}

/* Reopen case function */
function reopen_case(id) {
    get_request_api('/manage/cases/reopen/' + id)
    .done((data) => {
        refresh_case_table();
        $('#modal_case_detail').modal('hide');
    });
}

/* Close case function */
function close_case(id) {
    swal({
        title: "Are you sure?",
        text: "Case ID " + id + " will be closed and will not appear in contexts anymore",
        icon: "warning",
        buttons: true,
        dangerMode: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, close it!'
    })
    .then((willClose) => {
        if (willClose) {
            get_request_api('/manage/cases/close/' + id)
            .done((data) => {
                refresh_case_table();
                $('#modal_case_detail').modal('hide');
            });
        }
    });
}


$(document).ready(function() {

    if ($('.nav-tabs').length > 0) { // if .nav-tabs exists
        var hashtag = window.location.hash;
        if (hashtag!='') {
            $('.nav-item > a').removeClass('active').removeClass('show');
            $('.nav-item > a[href="'+hashtag+'"]').addClass('active');
             $('.nav-item > a[href="'+hashtag+'"]').addClass('show');
            $('.tab-content > div').removeClass('active');
            $(hashtag).addClass('active'); $(hashtag).addClass('show');
        }
    }

});