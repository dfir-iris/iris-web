var modal_group_table;
var current_groups_list;
manage_groups_table = $('#groups_table').dataTable( {
    "order": [[ 1, "asc" ]],
    "autoWidth": true,
    "columns": [
        {
            "data": "group_id",
            "render": function ( data, type, row ) {
                if (type === 'display') {
                    data = sanitizeHTML(data)
                    return '<a href="#" onclick="group_detail(\'' + row["group_id"] + '\');">' + data +'</a>';
                }
                return data;
            }
        },
        { "data": "group_name",
          "render": function ( data, type, row ) {
                if (type === 'display') {
                    data = sanitizeHTML(data)
                    return '<a href="#" onclick="group_detail(\'' + row["group_id"] + '\');">' + data +'</a>';
                }
                return data;
            }
        },
        { "data": "group_description",
          "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
        },
        { "data": "group_permissions_list",
          "render": function (data, type, row, meta) {
                if (type === 'display') {
                    tags = "";
                    for (perm in data) {
                        permstr = sanitizeHTML(data[perm].name);
                        tags += '<span class="badge badge-pill badge-light" title="Value 0x'+ data[perm].value.toString(16) +'">'+ permstr + '</span> ';
                    }
                    return tags;
                }
                return data;
              }
        },
        { "data": "group_members",
            "render": function ( data, type, row ) {
                if (type === 'display') {
                    return data.length;
                }
                return data;
            }
        }
      ]
    }
);

function refresh_groups(do_notify) {

    get_request_api('groups/list')
    .done((data) => {
        if(notify_auto_api(data, true)) {
            current_groups_list = data.data;
            manage_groups_table.api().clear().rows.add(data.data).draw();

            if (do_notify !== undefined) {
                notify_success("Refreshed");
            }

        }
    });

}


/* Fetch the details of an user and allow modification */
function group_detail(group_id) {
    url = 'groups/' + group_id + '/modal' + case_param();
    $('#modal_access_control').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_group').on("click", function () {
            clear_api_error();

            var data_sent = $('#form_new_group').serializeObject();
            post_request_api('/manage/groups/update/' + group_id, JSON.stringify(data_sent))
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_groups();
                    $('#modal_access_control').modal('hide');
                }
            });

            return false;
        })


    });
    $('#modal_access_control').modal({ show: true });
}

function add_group() {
    url = '/manage/groups/add/modal' + case_param();
    $('#modal_access_control').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_group').on("click", function () {
             clear_api_error();
            var data_sent = $('#form_new_group').serializeObject();
            post_request_api('/manage/groups/add', JSON.stringify(data_sent))
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_groups();
                    $('#modal_access_control').modal('hide');
                }
            });
        });
        $('#modal_access_control').modal({ show: true });
    });
}

function delete_group(id) {

    swal({
      title: "Are you sure?",
      text: "You won't be able to revert this!\nPlease make sure a group remains with enough rights to avoid a lockdown!",
      icon: "warning",
      buttons: true,
      dangerMode: true,
      confirmButtonColor: '#3085d6',
      cancelButtonColor: '#d33',
      confirmButtonText: 'Yes, delete it!'
    })
    .then((willDelete) => {
      if (willDelete) {
        var data_sent = {
            "csrf_token": $('#csrf_token').val()
        }
        post_request_api('/manage/groups/delete/' + id, JSON.stringify(data_sent))
        .done((data) => {
            if(notify_auto_api(data)) {
                refresh_groups();
                $('#modal_access_control').modal('hide');
            }
        });
      }
    });
}

function remove_members_from_group(group_id, user_id, on_finish) {

    swal({
      title: "Are you sure?",
      text: "This will remove the user from the group",
      icon: "warning",
      buttons: true,
      dangerMode: true,
      confirmButtonColor: '#3085d6',
      cancelButtonColor: '#d33',
      confirmButtonText: 'Yes, remove it!'
    })
    .then((willDelete) => {
        if (willDelete) {
            url = '/manage/groups/' + group_id + '/members/delete/' + user_id;
             var data_sent = {
                "csrf_token": $('#csrf_token').val()
             }
            post_request_api(url, JSON.stringify(data_sent))
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_groups();
                    refresh_group_members(group_id);

                    if (on_finish !== undefined) {
                        on_finish();
                    }

                }
            });
        }
    });

}

function add_members_to_group(group_id) {
    url = 'groups/' + group_id + '/members/modal' + case_param();
    $('#modal_ac_additional').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#save_group_members').on("click", function () {
            clear_api_error();

            var data_sent = Object();
            data_sent['group_members'] = $('#group_members').val();
            data_sent['csrf_token'] = $('#csrf_token').val();

            post_request_api('groups/' + group_id + '/members/update', JSON.stringify(data_sent))
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_groups();
                    refresh_group_members(group_id);
                    $('#modal_ac_additional').modal('hide');
                }
            });

            return false;
        });
        $('#modal_ac_additional').modal({ show: true });
    });
}

function refresh_group_members(group_id) {
    if (modal_group_table !== undefined) {
        get_request_api('/manage/groups/' + group_id)
        .done((data) => {
            if(notify_auto_api(data)) {
                modal_group_table.clear();
                modal_group_table.rows.add(data.data.group_members).draw();
            }
        });
    }
}

function refresh_group_cac(group_id) {
    if (modal_group_cac_table !== undefined) {
        get_request_api('/manage/groups/' + group_id)
        .done((data) => {
            if(notify_auto_api(data)) {
                current_group_cases_access_list = data.data.group_cases_access;
                modal_group_cac_table.clear();
                modal_group_cac_table.rows.add(current_group_cases_access_list).draw();
            }
        });
    }
}

function manage_group_cac(group_id) {
    url = 'groups/' + group_id + '/cases-access/modal' + case_param();

    $('#manage_group_cac_button').text('Loading manager...');

    $('#modal_ac_additional').load(url, function (response, status, xhr) {
        $('#manage_group_cac_button').text('Set case access');
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#grant_case_access_to_group').on("click", function () {
            clear_api_error();

            var data_sent = Object();
            data_sent['access_level'] = parseInt($('#group_case_ac_select').val());
            data_sent['cases_list'] = $('#group_case_access_select').val();
            data_sent['auto_follow_cases'] = $('#enable_auto_follow_cases').is(':checked');
            data_sent['csrf_token'] = $('#csrf_token').val();

            window.swal({
                  title: "Updating access",
                  text: "Please wait. We are updating users access.",
                  icon: "/static/assets/img/loader_cubes.gif",
                  button: false,
                  allowOutsideClick: false
            });

            post_request_api('groups/' + group_id + '/cases-access/update', JSON.stringify(data_sent))
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_group_cac(group_id);
                    $('#modal_ac_additional').modal('hide');
                }
            })
            .always(() => {
                window.swal.close();
            });

            return false;
        });
        $('#modal_ac_additional').modal({ show: true });
    });
}

function remove_case_access_from_group(group_id, case_id, on_finish) {
     remove_cases_access_group(group_id, [case_id], on_finish);
}

function remove_group_cases_from_group_table(group_id, rows) {
    cases = [];
    for (cid in rows) {
        cases.push(rows[cid].case_id);
    }
    remove_cases_access_group(group_id, cases);
}

function remove_cases_access_group(group_id, cases, on_finish) {

    swal({
        title: "Are you sure?",
        text: "Members of this group won't be able to access these cases anymore",
        icon: "warning",
        buttons: true,
        dangerMode: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, remove them!'
    }).then((willDelete) => {
        if (willDelete) {
            url = '/manage/groups/' + group_id + '/cases-access/delete';

            window.swal({
              title: "Updating access",
              text: "Please wait. We are updating users access.",
              icon: "/static/assets/img/loader_cubes.gif",
              button: false,
              allowOutsideClick: false
            });
            var data_sent = Object();
            data_sent['cases'] = cases;
            data_sent['csrf_token'] = $('#csrf_token').val();

            post_request_api(url, JSON.stringify(data_sent))
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_group_cac(group_id);
                    if (on_finish !== undefined) {
                        on_finish();
                    }
                }
            })
            .always(() => {
                window.swal.close();
            });
        }
    });
}



$(document).ready(function () {
    refresh_groups();
});