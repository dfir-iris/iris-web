
function add_protagonist() {
    prota_html = $('#protagonist_list_edit_template').html();
    $('#protagonist_list_edit').append(prota_html);
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

function edit_case_info() {
    $('#case_gen_info_content').hide();
    $('#case_gen_info_edit').show();
    $('#cancel_case_info').show();
    $('#save_case_info').show();
    $('#case_info').hide();
}

function cancel_case_edit() {
    $('#case_gen_info_content').show();
    $('#case_gen_info_edit').hide();
    $('#cancel_case_info').hide();
    $('#case_info').show();
    $('#cancel_case_info').hide();
}

function save_case_edit(case_id) {

    var data_sent = $('form#form_update_case').serializeObject();
    var map_protagonists = Object();

    for (e in data_sent) {
        if (e.startsWith('protagonist_role_')) {
            map_protagonists[e.replace('protagonist_role_', '')] = {
                'role': data_sent[e]
            };
            delete data_sent[e];
        }
        if (e.startsWith('protagonist_name_')) {
            map_protagonists[e.replace('protagonist_name_', '')]['name'] = data_sent[e];
            delete data_sent[e];
        }
        if (e.startsWith('protagonist_contact_')) {
            map_protagonists[e.replace('protagonist_contact_', '')]['contact'] = data_sent[e];
            delete data_sent[e];
        }
        if (e.startsWith('protagonist_id_')) {
            map_protagonists[e.replace('protagonist_id_', '')]['id'] = data_sent[e];
            delete data_sent[e];
        }
    }
    data_sent['protagonists'] = [];
    for (e in map_protagonists) {
        data_sent['protagonists'].push(map_protagonists[e]);
    }

    data_sent['case_tags'] = $('#case_tags').val();

    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;

    data_sent['csrf_token'] = $('#csrf_token').val();

    post_request_api('/manage/cases/update', JSON.stringify(data_sent), true, undefined, case_id)
    .done((data) => {
        if(notify_auto_api(data)) {
            case_detail(case_id);
        }
    });
}

function remove_case_access_from_user(user_id, case_id, on_finish) {
    swal({
      title: "Are you sure?",
      text: "This user might not be able access this case anymore",
      icon: "warning",
      buttons: true,
      dangerMode: true,
      confirmButtonColor: '#3085d6',
      cancelButtonColor: '#d33',
      confirmButtonText: 'Yes, remove it!'
    })
    .then((willDelete) => {
        if (willDelete) {
            url = '/manage/users/' + user_id + '/case-access/delete';

            var data_sent = Object();
            data_sent['case'] = case_id;
            data_sent['csrf_token'] = $('#csrf_token').val();


            post_request_api(url, JSON.stringify(data_sent))
            .done((data) => {
                if(notify_auto_api(data)) {

                    if (on_finish !== undefined) {
                        on_finish();
                    }

                }
            }).always(() => {
                window.swal.close();
            });
        }
    });
}

function remove_cases_access_user(user_id, cases, on_finish) {

    swal({
      title: "Are you sure?",
      text: "This user might not be able access these cases anymore",
      icon: "warning",
      buttons: true,
      dangerMode: true,
      confirmButtonColor: '#3085d6',
      cancelButtonColor: '#d33',
      confirmButtonText: 'Yes, remove it!'
    })
    .then((willDelete) => {
        if (willDelete) {
            url = '/manage/users/' + user_id + '/cases-access/delete';

            var data_sent = Object();
            data_sent['cases'] = cases;
            data_sent['csrf_token'] = $('#csrf_token').val();


            post_request_api(url, JSON.stringify(data_sent))
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_user_cac(user_id);

                    if (on_finish !== undefined) {
                        on_finish();
                    }

                }
            }).always(() => {
                window.swal.close();
            });
        }
    });

}