function add_asset_type() {
    url = '/manage/asset-type/add/modal' + case_param();
    $('#modal_add_type_content').load(url, function () {

        $('#submit_new_assettype').on("click", function () {
            event.preventDefault();
            var form = $('#form_new_asset_type').serializeObject();

            $.ajax({
                url: '/manage/asset-type/add' + case_param(),
                type: "POST",
                data: JSON.stringify(form),
                dataType: "json",
                contentType: "application/json;charset=UTF-8",
                cache: false,
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
                    propagate_form_api_errors(error.responseJSON.data);
                }
            });

            return false;
        })
    });
    $('#modal_add_type').modal({ show: true });
}

$('#assets_table').dataTable( {
    "ajax": {
      "url": "/manage/asset-type/list" + case_param(),
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
                "data": "asset_name",
                "render": function ( data, type, row ) {
                    return '<a href="#" onclick="assettype_detail(\'' + row['asset_id'] + '\');">' + sanitizeHTML(data) +'</a>';
                }
            },
            {
                "data": "asset_description",
                "render": function ( data, type, row ) {
                    if (type === 'display') { data = sanitizeHTML(data);}
                    return data;
                }
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
    url = '/manage/asset-type/update/' + asset_id + '/modal' + case_param();
    $('#modal_add_type_content').load(url, function () {

        $('#submit_new_assettype').on("click", function () {
            event.preventDefault();
            var form = $('#form_new_asset_type').serializeObject();

            $.ajax({
                url:  '/manage/asset-type/update/' + asset_id + case_param(),
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
                            refresh_asset_table();
                            $('#modal_add_type').modal('hide');
                        });

                    } else {
                        $('#modal_add_type').text('Save again');
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
              url: '/manage/asset-type/delete/' + id + case_param(),
              type: "GET",
              dataType: 'JSON',
              success: function (data) {
                  if (data.status == 'success') {
                      swal(data.message, {
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
                  swal ( "Oh no !" ,  error.responseJSON.message ,  "error" );
              }
          });
      } else {
        swal("Pfew, that's was close");
      }
    });
}

/***    IOC Type     ***/

function add_ioc_type() {
    url = '/manage/ioc-types/add/modal' + case_param();
    $('#modal_add_type_content').load(url, function () {

        $('#submit_new_ioc_type').on("click", function () {
            var form = $('form#form_new_ioc_type').serializeObject();

            $.ajax({
                url: '/manage/ioc-types/add' + case_param(),
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
                            refresh_ioc_table();
                            $('#modal_add_type').modal('hide');

                        });
                    } else {
                        $('#modal_add_type').text('Save again');
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

$('#ioc_table').dataTable({
    "ajax": {
      "url": "/manage/ioc-types/list" + case_param(),
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
    "order": [[ 0, "asc" ]],
    "autoWidth": false,
    "columns": [
        {
            "data": "type_name",
            "render": function ( data, type, row ) {
                return '<a href="#" onclick="ioc_type_detail(\'' + row['type_id'] + '\');">' + sanitizeHTML(data) +'</a>';
            }
        },
        {
            "data": "type_description",
            "render": function ( data, type, row ) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
            }
        },
        {
            "data": "type_taxonomy",
            "render": function ( data, type, row ) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
            }
        }
    ]
 });

function refresh_ioc_table() {
  $('#ioc_table').DataTable().ajax.reload();
  notify_success("Refreshed");
}


/* Fetch the details of an asset and allow modification */
function ioc_type_detail(ioc_id) {
    url = '/manage/ioc-types/update/' + ioc_id + '/modal' + case_param();
    $('#modal_add_type_content').load(url, function () {

        $('#submit_new_ioc_type').on("click", function () {
            var form = $('form#form_new_ioc_type').serializeObject();

            $.ajax({
                url:  '/manage/ioc-types/update/' + ioc_id + case_param(),
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
                            refresh_ioc_table();
                            $('#modal_add_type').modal('hide');
                        });

                    } else {
                        $('#modal_add_type').text('Save again');
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

function delete_ioc_type(id) {

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
              url: '/manage/ioc-types/delete/' + id + case_param(),
              type: "GET",
              dataType: 'JSON',
              success: function (data) {
                  if (data.status == 'success') {
                      swal(data.message, {
                          icon: "success",
                          timer: 500
                      }).then((value) => {
                          refresh_ioc_table();
                          $('#modal_add_type').modal('hide');
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