function add_asset_type() {
    url = '/manage/asset-type/add/modal' + case_param();
    $('#modal_add_type_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        $('#form_new_asset_type').submit("click", function (event) {


            event.preventDefault();
            var formData = new FormData(this);

            url = '/manage/asset-type/add' + case_param();

            $.ajax({
                url: url,
                type: "POST",
                data: formData,
                cache: false,
                contentType: false,
                processData: false,
                success: function (data) {
                    if(notify_auto_api(data, true)) {
                            refresh_asset_table();
                            $('#modal_add_type').modal('hide');
                    }
                },
                error: function (error) {
                    $('#modal_add_type').text('Save');
                    propagate_form_api_errors(error.responseJSON.data);
                }
            });

            return false;
    });
    $('#modal_add_type').modal({ show: true });
})};

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
            },
            {
                "data": "asset_icon_not_compromised_path",
                "render": function ( data, type, row ) {
                    if (type === 'display') { data = sanitizeHTML(data);}
                    return '<img style="width:2em;height:2em" src=\'' + data + '\'>';

                }
            },
            {
                "data": "asset_icon_compromised_path",
                "render": function ( data, type, row ) {
                    if (type === 'display') { data = sanitizeHTML(data);}
                    return '<img style="width:2em;height:2em" src=\'' + data + '\'>';
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
    $('#modal_add_type_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#form_new_asset_type').submit("click", function (event) {
            event.preventDefault();
            var formData = new FormData(this);

            url = '/manage/asset-type/update/' + asset_id + case_param();

            $.ajax({
                url: url,
                type: "POST",
                data: formData,
                cache: false,
                contentType: false,
                processData: false,
                success: function (data) {
                  if(notify_auto_api(data, true)) {
                        refresh_asset_table();
                        $('#modal_add_type').modal('hide');
                  }
                },
                error: function (jqXHR) {
                    if(jqXHR.responseJSON && jqXHR.status == 400) {
                        propagate_form_api_errors(jqXHR.responseJSON.data);
                    } else {
                        ajax_notify_error(jqXHR, this.url);
                    }
                }
            });

            return false;
        });
        $('#modal_add_type').modal({ show: true });
    });
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
            get_request_api('/manage/asset-type/delete/' + id)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_asset_table();
                    $('#modal_add_type').modal('hide');
                }
            });
        } else {
            swal("Pfew, that was close");
        }
    });
}

/***    IOC Type     ***/

function add_ioc_type() {
    url = '/manage/ioc-types/add/modal' + case_param();
    $('#modal_add_type_content').load(url, function () {

        $('#submit_new_ioc_type').on("click", function () {
            var form = $('form#form_new_ioc_type').serializeObject();

            post_request_api('/manage/ioc-types/add', JSON.stringify(form), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_ioc_table();
                    $('#modal_add_type').modal('hide');
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
        },
        {
            "data": "type_validation_regex",
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
    $('#modal_add_type_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_ioc_type').on("click", function () {
            var form = $('form#form_new_ioc_type').serializeObject();

            post_request_api('/manage/ioc-types/update/' + ioc_id, JSON.stringify(form), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_ioc_table();
                    $('#modal_add_type').modal('hide');
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
            get_request_api('/manage/ioc-types/delete/' + id)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_ioc_table();
                    $('#modal_add_type').modal('hide');
                }
            });
      } else {
        swal("Pfew, that was close");
      }
    });
}
