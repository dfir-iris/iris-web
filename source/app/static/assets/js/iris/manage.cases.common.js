function refresh_case_table() {
    if ($('#cases_table').length === 0) {
        return false;
    }
    $('#cases_table').DataTable().ajax.reload();
    $('#cases_table').DataTable().columns.adjust().draw();
    notify_success('Cases list refreshed');
    return true;
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
            post_request_api('/manage/cases/close/' + id)
            .done((data) => {
                if (!refresh_case_table()) {
                    window.location.reload();
                }
                $('#modal_case_detail').modal('hide');
            });
        }
    });
}

/* Reopen case function */
function reopen_case(id) {
    post_request_api('/manage/cases/reopen/' + id)
    .done((data) => {
        if (!refresh_case_table()) {
            window.location.reload();
        }
        $('#modal_case_detail').modal('hide');
    });
}

/* Remove case function */
function remove_case(id) {

    swal({
        title: "Are you sure?",
        text: "You are about to delete this case forever. This cannot be reverted.\nAll associated data will be deleted",
        icon: "warning",
        buttons: true,
        dangerMode: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, delete it!'
    })
        .then((willDelete) => {
            if (willDelete) {
                post_request_api('/manage/cases/delete/' + id)
                .done((data) => {
                    if (notify_auto_api(data)) {
                        if (!refresh_case_table()) {
                            swal({
                                title: "Done!",
                                text: "You will be redirected in 5 seconds",
                                icon: "success",
                                buttons: false,
                                dangerMode: false
                            })
                            setTimeout(function () {
                                window.location.href = '/dashboard?cid=1';
                            }, 4500);
                        } else {
                            refresh_case_table();
                            $('#modal_case_detail').modal('hide');
                        }
                    }
                });
            } else {
                swal("Pfew, that was close");
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
    $('#save_case_info').hide();
    $('#case_info').show();
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

    post_request_api('/manage/cases/update/' + case_id, JSON.stringify(data_sent), true, undefined, case_id)
    .done((data) => {
        if(notify_auto_api(data)) {
            case_detail(case_id);
        }
    });
}

function add_protagonist() {
    random_string = Math.random().toString(36).substring(7);
    prota_html = $('#protagonist_list_edit_template').html();
    prota_html = prota_html.replace(/__PROTAGONIST_ID__/g, random_string);
    $('#protagonist_list_edit').append(prota_html);
}

function remove_protagonist(id) {
    $('#protagonist_' + id).remove();
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

var access_levels = [
    { "id": 1, "name": "Deny all" },
    { "id": 2, "name": "Read only" },
    { "id": 4, "name": "Full access" }
]

function get_access_level_options(data) {
    var options = "";

    for (var i = 0; i < access_levels.length; i++) {
        options += `<option value="${access_levels[i].id}" ${data == access_levels[i].id ? 'selected' : ''}>${access_levels[i].name}</option>`;
    }
    return options;
}

function update_user_case_access_level(user_id, case_id, access_level) {
    var data = {
        "case_id": parseInt(case_id),
        "user_id": parseInt(user_id),
        "access_level": parseInt(access_level),
        "csrf_token": $('#csrf_token').val()
    };

    post_request_api('/case/access/set-user', JSON.stringify(data), false, null, case_id)
    .done((data) => {
        notify_auto_api(data);
    });
}


function view_case_access_via_group(case_id) {
    url = '/case/groups/access/modal' + case_param();
    $('#modal_ac_additional').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        $('#modal_ac_additional').modal({ show: true });
    });
}

function set_case_access_via_group(case_id) {
    let case_groups_select = $('#group_case_access_select').val();

    case_groups_select.forEach(function(group_id) {
        let data = {
            "case_id": parseInt(case_id),
            "access_level": parseInt($('#group_case_ac_select').val()),
            "group_id": parseInt(group_id),
            "csrf_token": $('#csrf_token').val()
        };

        post_request_api('/case/access/set-group', JSON.stringify(data))
        .done((data) => {
            notify_auto_api(data);
            access_case_info_reload(case_id);
            $('#modal_ac_additional').modal('hide');
        });

    });
}


function access_case_info_reload(case_id, owner_id, reviewer_id) {
    var req_users = [];

    get_request_api('/case/users/list')
    .done((data) => {
         has_table = $.fn.dataTable.isDataTable( '#case_access_users_list_table' );
        if (!notify_auto_api(data, !has_table)) {
            return;
        }

        req_users = data.data;
        if ( has_table ) {
            table = $('#case_access_users_list_table').DataTable();
            table.clear();
            table.rows.add(req_users);
            table.draw();
        } else {
            addFilterFields($('#case_access_users_list_table').attr("id"));
            $("#case_access_users_list_table").DataTable({
                    dom: '<"container-fluid"<"row"<"col"l><"col"f>>>rt<"container-fluid"<"row"<"col"i><"col"p>>>',
                    aaData: req_users,
                    aoColumns: [
                      {
                        "data": "user_id",
                        "className": "dt-center"
                    },
                    {
                        "data": "user_name",
                        "className": "dt-center",
                        "render": function (data, type, row, meta) {
                            if (type === 'display') { data = sanitizeHTML(data);}
                            return data;
                        }
                    },
                    {
                        "data": "user_login",
                        "className": "dt-center",
                        "render": function (data, type, row, meta) {
                            if (type === 'display') { data = sanitizeHTML(data);}
                            return data;
                        }
                    },
                    {
                        "data": "user_access_level",
                        "className": "dt-center",
                        "render": function ( data, type, row ) {
                            return `<select class="form-control" onchange="update_user_case_access_level('${row.user_id}',${case_id},this.value)">${get_access_level_options(data)}</select>`;
                        }
                    }
                    ],
                    filter: true,
                    info: true,
                    ordering: true,
                    processing: true,
                    initComplete: function () {
                        tableFiltering(this.api(), 'case_access_users_list_table');
                    }
            });
        }
        let quick_owner = $('#case_quick_owner');
        let quick_reviewer = $('#case_quick_reviewer');
        quick_reviewer.append($('<option>'));


        for (let i = 0; i < req_users.length; i++) {
            $('#username-list').append($('<option>', {
                value: req_users[i].user_name
            }));
            $('#emails-list').append($('<option>', {
                value: req_users[i].user_email
            }));

            quick_owner.append($('<option>', {
                value: req_users[i].user_id,
                text: req_users[i].user_name
            }));
            if (req_users[i].user_id == owner_id) {
                quick_owner.val(req_users[i].user_id);
            }
            quick_owner.selectpicker('refresh');
            quick_reviewer.append($('<option>', {
                value: req_users[i].user_id,
                text: req_users[i].user_name
            }));
            if (req_users[i].user_id == reviewer_id) {
                quick_reviewer.val(req_users[i].user_id);
            }
            quick_reviewer.selectpicker('refresh');
        }
    });

    set_suggest_tags('case_tags');
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