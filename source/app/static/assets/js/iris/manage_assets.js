function add_asset_type() {
    url = 'assettype/add/modal' + case_param();
    $('#modal_add_type_content').load(url, function () {

        $('#submit_new_assettype').on("click", function () {
            var form = $('#form_new_asset_type').serializeObject();

            $.ajax({
                url: 'assettype/add' + case_param(),
                type: "POST",
                data: JSON.stringify(form),
                dataType: "json",
                contentType: "application/json;charset=UTF-8",
                cache: false,
                success: function (data) {
                    console.log(data);
                    if (data.status == 'success') {
                        swal("Done !",
                        "Your asset has been created successfully",
                            {
                                icon: "success",
                                timer: 2000
                            }
                        ).then((value) => {
                            refresh_asset_table();
                            $('#modal_add_type').modal('hide');

                        });
                    } else {
                        $('#modal_add_type').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    $('#modal_add_type').text('Save');
                    notify_error(error.responseJSON.message);
                }
            });

            return false;
        })
    });
    $('#modal_add_type').modal({ show: true });
}

$('#assets_table').dataTable( {
    "ajax": {
      "url": "assettype/list" + case_param(),
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
    "columnDefs": [
        {
            "render": function ( data, type, row ) {
                return '<a href="#" onclick="assettype_detail(\'' + row[2] + '\');">' + data +'</a>';
            },
            "targets": 0
        }
      ]
    }
);

function refresh_asset_table() {
  $('#assets_table').DataTable().ajax.reload();
  notify_success("Refreshed");
}


/* Fetch the details of an asset and allow modification */
function assettype_detail(asset_id) {
    url = 'assettype/update/' + asset_id + '/modal' + case_param();
    $('#modal_add_type_content').load(url, function () {

        $('#submit_new_assettype').on("click", function () {
            var form = $('#form_new_asset_type').serializeObject();

            $.ajax({
                url:  'assettype/update/' + asset_id + case_param(),
                type: "POST",
                data: JSON.stringify(form),
                dataType: "json",
                contentType: "application/json;charset=UTF-8",
                success: function (data) {
                    if (data.status == 'success') {
                        swal("You're set !",
                            "The asset has been updated successfully",
                            {
                                icon: "success",
                                timer: 1500
                            }
                        ).then((value) => {
                            refresh_asset_table();
                            $('#modal_add_type').modal('hide');
                        });

                    } else {
                        $('#modal_add_type').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    notify_error(error.responseJSON.message);
                }
            });

            return false;
        })


    });
    $('#modal_add_type').modal({ show: true });
}

function delete_asset_type(id) {

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
              url: '/manage/assettype/delete/' + id + case_param(),
              type: "GET",
              dataType: 'JSON',
              success: function (data) {
                  if (data.status == 'success') {
                      swal("Asset type deleted !", {
                          icon: "success",
                          timer: 500
                      }).then((value) => {
                          refresh_asset_table();
                          $('#modal_add_type').modal('hide');
                      });
                  } else {
                      swal ( "Oh no !" ,  data.message ,  "error" );
                  }
              },
              error: function (error) {
                  swal ( "Oh no !" ,  error ,  "error" );                
              }
          });
      } else {
        swal("Pfew, that's was close");
      }
    });
}