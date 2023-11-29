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
            post_request_api('/manage/asset-type/delete/' + id)
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
    let url = '/manage/ioc-types/add/modal' + case_param();
    $('#modal_add_type_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

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
        $('#modal_add_type').modal({ show: true });
    });

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
            post_request_api('/manage/ioc-types/delete/' + id)
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

/***    Classification    ***/

function add_classification() {
    url = '/manage/case-classifications/add/modal' + case_param();
    $('#modal_add_type_content').load(url, function () {

        $('#submit_new_case_classification').on("click", function () {
            var form = $('form#form_new_case_classification').serializeObject();

            post_request_api('/manage/case-classifications/add', JSON.stringify(form), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_classification_table();
                    $('#modal_add_type').modal('hide');
                }
            });

            return false;
        })
    });
    $('#modal_add_type').modal({ show: true });
}

$('#classification_table').dataTable({
    "ajax": {
      "url": "/manage/case-classifications/list" + case_param(),
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
            "data": "name",
            "render": function ( data, type, row ) {
                return '<a href="#" onclick="classification_detail(\'' + row['id'] + '\');">' + sanitizeHTML(data) +'</a>';
            }
        },
        {
            "data": "name_expanded",
            "render": function ( data, type, row ) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
            }
        },
        {
            "data": "description",
            "render": function ( data, type, row ) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
            }
        }
    ]
 });

function refresh_classification_table() {
  $('#classification_table').DataTable().ajax.reload();
  notify_success("Refreshed");
}

/* Fetch the details of an classification and allow modification */
function classification_detail(ioc_id) {
    url = '/manage/case-classifications/update/' + ioc_id + '/modal' + case_param();
    $('#modal_add_type_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_case_classification').on("click", function () {
            var form = $('form#form_new_case_classification').serializeObject();

            post_request_api('/manage/case-classifications/update/' + ioc_id, JSON.stringify(form), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_classification_table();
                    $('#modal_add_type').modal('hide');
                }
            });

            return false;
        })


    });
    $('#modal_add_type').modal({ show: true });
}
function delete_case_classification(id) {

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
            post_request_api('/manage/case-classifications/delete/' + id)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_classification_table();
                    $('#modal_add_type').modal('hide');
                }
            });
      } else {
        swal("Pfew, that was close");
      }
    });
}


/***    State    ***/

function add_state() {
    url = '/manage/case-states/add/modal' + case_param();
    $('#modal_add_type_content').load(url, function () {

        $('#submit_new_case_state').on("click", function () {
            var form = $('form#form_new_case_state').serializeObject();

            post_request_api('/manage/case-states/add', JSON.stringify(form), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_state_table();
                    $('#modal_add_type').modal('hide');
                }
            });

            return false;
        })
    });
    $('#modal_add_type').modal({ show: true });
}

$('#state_table').dataTable({
    "ajax": {
      "url": "/manage/case-states/list" + case_param(),
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
            "data": "state_name",
            "render": function ( data, type, row ) {
                if (type === 'display') {
                    if (row['protected'] === true) {
                        return '<span href="#" "><i class="fa fa-lock mr-2" title="Protected state"></i>' + sanitizeHTML(data) + '</span>';
                    }
                    return '<a href="#" onclick="state_detail(\'' + row['state_id'] + '\');">' + sanitizeHTML(data) + '</a>';
                }
                return data;
            }
        },
        {
            "data": "state_description",
            "render": function ( data, type, row ) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
            }
        }
    ]
 });

function refresh_state_table() {
  $('#state_table').DataTable().ajax.reload();
  notify_success("Refreshed");
}

/* Fetch the details of an state and allow modification */
function state_detail(ioc_id) {
    url = '/manage/case-states/update/' + ioc_id + '/modal' + case_param();
    $('#modal_add_type_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_case_state').on("click", function () {
            var form = $('form#form_new_case_state').serializeObject();

            post_request_api('/manage/case-states/update/' + ioc_id, JSON.stringify(form))
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_state_table();
                    $('#modal_add_type').modal('hide');
                }
            });

            return false;
        })


    });
    $('#modal_add_type').modal({ show: true });
}
function delete_case_state(id) {

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
            post_request_api('/manage/case-states/delete/' + id)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_state_table();
                    $('#modal_add_type').modal('hide');
                }
            });
      } else {
        swal("Pfew, that was close");
      }
    });
}



/***    Evidence types    ***/

function add_evidence_type() {
    var url = '/manage/evidence-types/add/modal' + case_param();
    $('#modal_add_type_content').load(url, function () {

        $('#submit_new_evidence_type').on("click", function () {
            var form = $('form#form_new_evidence_type').serializeObject();

            post_request_api('/manage/evidence-types/add', JSON.stringify(form), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_evidence_table();
                    $('#modal_add_type').modal('hide');
                }
            });

            return false;
        })
    });
    $('#modal_add_type').modal({ show: true });
}

$('#evidence_table').dataTable({
    "ajax": {
      "url": "/manage/evidence-types/list" + case_param(),
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
            "data": "name",
            "render": function ( data, type, row ) {
                return '<a href="#" onclick="evidence_detail(\'' + row['id'] + '\');">' + sanitizeHTML(data) +'</a>';
            }
        },
        {
            "data": "description",
            "render": function ( data, type, row ) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
            }
        }
    ]
 });

function refresh_evidence_table() {
  $('#evidence_table').DataTable().ajax.reload();
  notify_success("Refreshed");
}

function evidence_detail(evidence_id) {
    let url = '/manage/evidence-types/update/' + evidence_id + '/modal' + case_param();
    $('#modal_add_type_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_evidence_type').on("click", function () {
            var form = $('form#form_new_evidence_type').serializeObject();

            post_request_api('/manage/evidence-types/update/' + evidence_id, JSON.stringify(form), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_evidence_table();
                    $('#modal_add_type').modal('hide');
                }
            });

            return false;
        })


    });
    $('#modal_add_type').modal({ show: true });
}
function delete_evidence_type(id) {

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
            post_request_api('/manage/evidence-types/delete/' + id)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_evidence_table();
                    $('#modal_add_type').modal('hide');
                }
            });
      } else {
        swal("Pfew, that was close");
      }
    });
}
