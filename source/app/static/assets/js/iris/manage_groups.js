$('#groups_table').dataTable( {
    "ajax": {
      "url": "groups/list" + case_param(),
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
  $('#groups_table').DataTable().ajax.reload();
  if (do_notify !== undefined) {
    notify_success("Refreshed");
  }
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
            post_request_api('/manage/groups/update/' + user_id, JSON.stringify(data_sent), true)
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

function delete_group(id) {

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
        get_request_api('/manage/groups/delete/' + id)
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

function add_members_to_group(group_id) {
    url = 'groups/' + group_id + '/members/modal' + case_param();
    $('#modal_ac_additional').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#save_group_members').on("click", function () {
            clear_api_error();

            var data_sent = $('#form_new_members').serializeObject();
            post_request_api('groups/' + group_id + '/members/update', JSON.stringify(data_sent), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_users();
                    $('#modal_ac_additional').modal('hide');
                }
            });

            return false;
        });
        $('#modal_ac_additional').modal({ show: true });
    });
}