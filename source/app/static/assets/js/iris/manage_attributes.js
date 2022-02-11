function add_object_attribute() {
    url = '/manage/attributes/add/modal' + case_param();
    $('#modal_add_attribute_content').load(url, function () {

        $('#submit_new_attribute').on("click", function () {
            var form = $('#form_new_attribute').serializeObject();

            $.ajax({
                url: '/manage/attributes/add' + case_param(),
                type: "POST",
                data: JSON.stringify(form),
                dataType: "json",
                contentType: "application/json;charset=UTF-8",
                success: function (data) {
                    console.log(data);
                    if (data.status == 'success') {
                        swal("Done !",
                            data.message,
                            {
                                icon: "success",
                                timer: 500
                            }
                        ).then((value) => {
                            refresh_attribute_table();
                            $('#modal_add_attribute').modal('hide');

                        });
                    } else {
                        $('#modal_add_attribute').text('Save again');
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
    $('#modal_add_type').modal({ show: true });
}

$('#attributes_table').dataTable( {
    "ajax": {
      "url": "/manage/attributes/list" + case_param(),
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
    "order": [[ 0, "desc" ]],
    "autoWidth": false,
    "columns": [
            {
                "data": "attribute_id",
                "render": function ( data, type, row ) {
                    return '<a href="#" onclick="attribute_detail(\'' + row['attribute_id'] + '\');">' + sanitizeHTML(data) +'</a>';
                }
            }
        ]
    }
);

function refresh_attribute_table() {
  $('#attributes_table').DataTable().ajax.reload();
  notify_success("Refreshed");
}

function attribute_detail(attr_id) {
    url = '/manage/attributes/update/' + attr_id + '/modal' + case_param();
    $('#modal_add_attribute_content').load(url, function () {

        $('#submit_new_attribute').on("click", function () {
            event.preventDefault();
            var form = $('#form_new_attribute').serializeObject();

            $.ajax({
                url:  '/manage/attributes/update/' + attr_id + case_param(),
                type: "POST",
                data: JSON.stringify(form),
                dataType: "json",
                contentType: "application/json;charset=UTF-8",
                success: function (data) {
                    if (data.status == 'success') {
                        swal("You're set !",
                            data.message,
                            {
                                icon: "success",
                                timer: 500
                            }
                        ).then((value) => {
                            refresh_attribute_table();
                            $('#modal_add_attribute').modal('hide');
                        });

                    } else {
                        $('#modal_add_attribute').text('Save again');
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
    $('#modal_add_attribute').modal({ show: true });
}

function delete_attribute(id) {

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
              url: '/manage/attributes/delete/' + id + case_param(),
              type: "GET",
              dataType: 'JSON',
              success: function (data) {
                  if (data.status == 'success') {
                      swal(data.message, {
                          icon: "success",
                          timer: 500
                      }).then((value) => {
                          refresh_attribute_table();
                          $('#modal_add_attribute').modal('hide');
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
