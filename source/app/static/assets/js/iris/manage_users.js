var current_users_list = [];
function add_user() {
    url = 'users/add/modal' + case_param();
    $('#modal_access_control').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_user').on("click", function () {

            var data_sent = $('#form_new_user').serializeObject()
            clear_api_error();

            post_request_api('users/add', JSON.stringify(data_sent), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_users();
                    $('#modal_access_control').modal('hide');
                }
            });

            return false;
        })
    });
    $('#modal_access_control').modal({ show: true });
}

manage_users_table = $('#users_table').dataTable( {
    "order": [[ 1, "asc" ]],
    "autoWidth": false,
    "language": {
        "emptyTable": "Loading users..."
    },
    "columns": [
        {
            "data": "user_id",
            "render": function ( data, type, row ) {
                if (type === 'display') {
                    data = sanitizeHTML(data)
                    return '<a href="#" onclick="user_detail(\'' + row["user_id"] + '\');">' + data +'</a>';
                }
                return data;
            }
        },
        { "data": "user_name",
          "render": function ( data, type, row ) {
                if (type === 'display') {
                    data = sanitizeHTML(data)
                    return '<a href="#" onclick="user_detail(\'' + row["user_id"] + '\');">' + data +'</a>';
                }
                return data;
            }
        },
        { "data": "user_login",
          "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
        },
        { "data": "user_email",
          "render": function (data, type, row, meta) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
              }
        },
        { "data": "user_active",
        "render": function (data, type, row, meta) {
            if (type === 'display') {
                data = sanitizeHTML(data);
                if (data == true) {
                    data = '<span class="badge ml-2 badge-success">Active</span>';
                } else {
                    data = '<span class="badge ml-2 badge-warning">Disabled</span>';
                }
            }
            return data;
          }
        }
      ]
    }
);

function refresh_users(do_notify) {

    get_request_api('users/list')
    .done((data) => {

        if(notify_auto_api(data, true)) {
            current_users_list = data.data;
            manage_users_table.api().clear().rows.add(data.data).draw();

            if (do_notify !== undefined) {
                notify_success("Refreshed");
            }

        }

    });

}


/* Fetch the details of an user and allow modification */
function user_detail(user_id, goto_tab) {
    url = 'users/' + user_id + '/modal' + case_param();
    $('#modal_access_control').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_user').on("click", function () {
            clear_api_error();

            var data_sent = $('#form_new_user').serializeObject();
            post_request_api('/manage/users/update/' + user_id, JSON.stringify(data_sent), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_users();
                    $('#modal_access_control').modal('hide');
                }
            });

            return false;
        })
        if (goto_tab !== undefined) {
            $('.nav-pills a[href="#'+ goto_tab +'"]').tab('show');
        }
        $('#modal_access_control').modal({ show: true });
    });

}

function delete_user(id) {

    swal({
      title: "Are you sure?",
      text: "You won't be able to revert this !",
      icon: "warning",
      buttons: true,
      dangerMode: true,
      confirmButtonColor: '#3085d6',
      cancelButtonColor: '#d33',
      confirmButtonText: 'Yes, delete it!'
    })
    .then((willDelete) => {
      if (willDelete) {
        get_request_api('/manage/users/delete/' + id)
        .done((data) => {
            if(notify_auto_api(data)) {
                refresh_users();
                $('#modal_access_control').modal('hide');
            }
        });
      } else {
        swal("Pfew, that was close");
      }
    });
}

function activate_user(id) {
  get_request_api('/manage/users/activate/' + id)
  .done((data) => {
    if(notify_auto_api(data)) {
        refresh_users();
        $('#modal_access_control').modal('hide');
    }
  });
}

function deactivate_user(id) {
  get_request_api('/manage/users/deactivate/' + id)
  .done((data) => {
    if(notify_auto_api(data)) {
        refresh_users();
        $('#modal_access_control').modal('hide');
    }
  });
}

function remove_member_from_org_wrap(org_id, user_id) {
    remove_members_from_org(org_id, user_id, function() {
        user_detail(user_id, 'user_orgs_tab');
    });
}

function remove_member_from_group_wrap(group_id, user_id) {
    remove_members_from_group(group_id, user_id, function() {
        user_detail(user_id, 'user_groups_tab');
    });
}

function manage_user_groups(user_id) {
    url = 'users/' + user_id + '/groups/modal' + case_param();
    $('#modal_access_control').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        $('#modal_access_control').modal({ show: true });

        $('#save_user_groups_membership').on("click", function () {
            clear_api_error();

            var data_sent = Object();
            data_sent['groups_membership'] = $('#user_groups_membership').val();
            data_sent['csrf_token'] = $('#csrf_token').val();

            post_request_api('/manage/users/' + user_id + '/groups/update', JSON.stringify(data_sent), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_groups();
                    user_detail(user_id, 'user_groups_tab');
                }
            });
        });
    });
}

$(document).ready(function () {
    refresh_users();
});