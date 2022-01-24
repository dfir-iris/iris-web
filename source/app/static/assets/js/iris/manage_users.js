
function add_user() {
    url = 'users/add/modal' + case_param();
    $('#modal_add_user_content').load(url, function () {

        $('#submit_new_user').on("click", function () {

            var data_sent = $('#form_new_user').serializeObject()
            clear_api_error();

            $.ajax({
                url: 'users/add' + case_param(),
                type: "POST",
                data: JSON.stringify(data_sent),
                contentType: "application/json;charset=UTF-8",
                dataType: "json",
                success: function (data) {
                    if (data.status == 'success') {
                        swal("Done !",
                        "User has been created successfully",
                            {
                                icon: "success",
                                timer: 500
                            }
                        ).then((value) => {
                            refresh_users();
                            $('#modal_add_user').modal('hide');

                        });
                    } else {
                        $('#submit_new_user').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    propagate_form_api_errors(error.responseJSON.data);
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

function refresh_users() {
  $('#users_table').DataTable().ajax.reload();
  notify_success("Refreshed");
}


/* Fetch the details of an user and allow modification */
function user_detail(user_id) {
    url = 'users/' + user_id + '/modal' + case_param();
    $('#modal_add_user_content').load(url, function () {

        $('#submit_new_user').on("click", function () {
            clear_api_error();

            var data_sent = $('#form_new_user').serializeObject();
            $.ajax({
                url: '/manage/users/update/' + user_id + case_param(),
                type: "POST",
                data: JSON.stringify(data_sent),
                contentType: "application/json;charset=UTF-8",
                dataType: "json",
                success: function (data) {
                    if (data.status == 'success') {
                        swal("You're set !",
                            "The user has been updated successfully",
                            {
                                icon: "success",
                                timer: 500
                            }
                        ).then((value) => {
                            refresh_users();
                            $('#modal_add_user').modal('hide');
                        });

                    } else {
                        $('#modal_add_user').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    propagate_form_api_errors(error.responseJSON.data);
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
          $.ajax({
              url: '/manage/users/delete/' + id + case_param(),
              type: "GET",
              success: function (data) {
                  if (data.status == 'success') {
                      swal("User deleted !", {
                          icon: "success",
                          timer: 500
                      }).then((value) => {
                          refresh_users();
                          $('#modal_add_user').modal('hide');
                      });
                  } else {
                      swal ( "Oh no !" ,  data.message ,  "error" );
                  }
              },
              error: function (error) {
                  swal ( "Oh no !" ,  error.responseJSON.message ,  "error" );
              }
          });
      } else {
        swal("Pfew, that's was close");
      }
    });
}

function activate_user(id) {
  $.ajax({
      url: '/manage/users/activate/' + id + case_param(),
      type: "GET",
      success: function (data) {
          if (data.status == 'success') {
              swal("User activated !", {
                  icon: "success",
                  timer: 500
              }).then((value) => {
                  refresh_users();
                  $('#modal_add_user').modal('hide');
              });
          } else {
              swal ( "Oh no !" ,  data.message ,  "error" );
          }
      },
      error: function (error) {
          swal ( "Oh no !" ,  error.responseJSON.message ,  "error" );
      }
  });
}

function deactivate_user(id) {
  $.ajax({
      url: '/manage/users/deactivate/' + id + case_param(),
      type: "GET",
      success: function (data) {
          if (data.status == 'success') {
              swal("User deactivated !", {
                  icon: "success",
                  timer: 500
              }).then((value) => {
                  refresh_users();
                  $('#modal_add_user').modal('hide');
              });
          } else {
              swal ( "Oh no !" ,  data.message ,  "error" );
          }
      },
      error: function (error) {
          swal ( "Oh no !" ,  error.responseJSON.message ,  "error" );
      }
  });
}