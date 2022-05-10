
function add_user() {
    url = 'users/add/modal' + case_param();
    $('#modal_add_user_content').load(url, function (response, status, xhr) {
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
                    $('#modal_add_user').modal('hide');
                }
            });

            return false;
        })
    });
    $('#modal_add_user').modal({ show: true });
}

$('#users_table').dataTable( {
    "ajax": {
      "url": "users/list" + case_param(),
      "contentType": "application/json",
      "type": "GET",
      "data": function ( d ) {
        if (d.status == 'success') {
          return JSON.stringify( d.data );
        } else {
          return [];
        }
      }
    },
    "order": [[ 1, "asc" ]],
    "autoWidth": false,
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
        { "data": "user_roles",
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
  $('#users_table').DataTable().ajax.reload();
  if (do_notify !== undefined) {
    notify_success("Refreshed");
  }
}


/* Fetch the details of an user and allow modification */
function user_detail(user_id) {
    url = 'users/' + user_id + '/modal' + case_param();
    $('#modal_add_user_content').load(url, function (response, status, xhr) {
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
                    $('#modal_add_user').modal('hide');
                }
            });

            return false;
        })


    });
    $('#modal_add_user').modal({ show: true });
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
                $('#modal_add_user').modal('hide');
            }
        });
      } else {
        swal("Pfew, that's was close");
      }
    });
}

function activate_user(id) {
  get_request_api('/manage/users/activate/' + id)
  .done((data) => {
    if(notify_auto_api(data)) {
        refresh_users();
        $('#modal_add_user').modal('hide');
    }
  });
}

function deactivate_user(id) {
  get_request_api('/manage/users/deactivate/' + id)
  .done((data) => {
    if(notify_auto_api(data)) {
        refresh_users();
        $('#modal_add_user').modal('hide');
    }
  });
}