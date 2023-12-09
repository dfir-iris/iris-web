const preventFormDefaultBehaviourOnSubmit = (event) => {
    event.preventDefault();
    return false;
};

$('#form_new_module').submit(function () {

    post_request_api('/manage/modules/add', $('form#form_new_module').serializeArray(), function() {
        $('#submit_new_module').text('Saving..')
            .attr("disabled", true)
            .removeClass('bt-outline-success')
            .addClass('btn-success', 'text-dark');
    })
    .done((data) => {
        notify_auto_api(data);
    })
    .always(() => {
         $('#submit_new_module')
        .attr("disabled", false)
        .addClass('bt-outline-success')
        .removeClass('btn-success', 'text-dark');
    });

    return false;
});


function add_module() {
    url = 'modules/add/modal' + case_param();
    $('#modal_add_module_content').load(url, function (response, status, xhr) {
        $('#form_new_module').on("submit", preventFormDefaultBehaviourOnSubmit);
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_module').on("click", function () {

            post_request_api('modules/add', JSON.stringify($('#form_new_module').serializeObject()), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_modules(true);
                    refresh_modules_hooks(true);
                    $('#modal_add_module').modal('hide');
                } else {
                    $('#alert_mod_add').text(data.message);
                    if (data.data) {
                        $('#details_list').empty();
                        for(var i in data.data)
                        {
                           var output='<li>'+data.data[i]+'</li>';
                           $('#details_list').append(output);
                        }

                        $('#alert_mod_details').show();
                    }
                    $('#alert_mod_add').show();
                    $('#submit_new_module').text("Retry");
                }
            })
            .fail((error) => {
                data = error.responseJSON;
                $('#submit_new_module').text('Save');
                $('#alert_mod_add').text(data.message);
                if (data.data && data.data.length > 0) {
                    $('#details_list').empty();
                    for(var i in data.data)
                    {
                       var output='<li>'+data.data[i]+'</li>';
                       $('#details_list').append(output);
                    }

                    $('#alert_mod_details').show();
                }
                $('#alert_mod_add').show();
                $('#submit_new_module').text("Retry");

            });

            return false;
        })
    });
    $('#modal_add_module').modal({ show: true });
}

$('#modules_table').dataTable( {
    "ajax": {
      "url": "modules/list" + case_param(),
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
      { 'data': 'id'},
      { 'data': 'module_human_name'},
      { 'data': 'has_pipeline',
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
      { 'data': 'module_version',
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
      { 'data': 'interface_version',
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
      { 'data': 'date_added',
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
      { 'data': 'name',
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
      { 'data': 'is_active'},

                        ],
    "columnDefs": [
        {
            "render": function ( data, type, row ) {
                data = sanitizeHTML(data);
                return '<a href="#" onclick="module_detail(\'' + row['id'] + '\');">' + data +'</a>';
            },
            "targets": [0, 1]
        },
        {
            "render": function ( data, type, row ) {
            if (data == true) {
                data = '<i class="fas fa-check text-success"></i>';
            } else {
               data = '<i class="fas fa-times text-warning"></i>';
            }
            if (row['configured'] == false) {
                return data + ' <i class="fas fa-exclamation-triangle text-warning" data-toggle="tooltip" data-placement="top" title="Module was disabled because mandatory settings are not set. Please configure to activate."></i>'
            } else { return data; }
            },
            "targets": [7]
        }
      ]
    }
);

function refresh_modules(silent) {
  $('#modules_table').DataTable().ajax.reload();
  $(function () {
    $('[data-toggle="tooltip"]').tooltip()
  })
  if (silent === undefined || silent !== true) {
     notify_success("Modules refreshed");
  }
}

$('#hooks_table').dataTable( {
    "ajax": {
      "url": "modules/hooks/list" + case_param(),
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
      { 'data': 'id'},
      { 'data': 'module_name',
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
      { 'data': 'hook_name',
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
      { 'data': 'hook_description',
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
        { 'data': 'is_manual_hook',
        "render": function (data, type, row, meta) {
            if (data == false) {
                    data = "<i class='fas fa-check text-success'></i>";
                } else {
                   data = "<i class='fas fa-times text-muted'></i>";
              }
            return data;
          }
        },
      { 'data': 'is_active',
        "render": function (data, type, row, meta) {
            if (data == true) {
                    data = "<i class='fas fa-check text-success'></i>";
                } else {
                   data = "<i class='fas fa-times text-muted'></i>";
              }
            return data;
          }
     }
    ]
    }
);

function refresh_modules_hooks(silent) {
  $('#hooks_table').DataTable().ajax.reload();
  if (silent === undefined || silent !== true) {
         notify_success("Hooks refreshed");
  }
}


function export_mod_config(module_id) {
    get_request_api('/manage/modules/export-config/' + module_id)
    .done((data) => {
        if(notify_auto_api(data, true)) {
            download_file(data.data.module_name + "_configuration_export.json", "text/json",
            JSON.stringify(data.data.module_configuration, null, 4));
        }
    });
}

function import_mod_config(module_id){

    var file = $("#input_configuration_file").get(0).files[0];
    var reader = new FileReader();
    reader.onload = function (e) {
        fileData = e.target.result
        var data = new Object();
        data['csrf_token'] = $('#csrf_token').val();
        data['module_configuration'] = fileData;

        post_request_api('/manage/modules/import-config/'+ module_id, JSON.stringify(data), true)
        .done((data) => {
            if(notify_auto_api(data, true)) {
                module_detail(module_id);
                $('#modal_input_config').modal('hide');
                swal("Got news for you", data.message, "success");
            } else {
                swal("Got bad news for you", data.data, "error");
            }
        });
    };
    reader.readAsText(file)

    return false;
}

/* Update the param of a module */
function update_param(module_id, param_name) {
    url = 'modules/get-parameter/' + decodeURIComponent(escape(window.btoa(param_name))) + case_param();
    $('#modal_update_param_content').load(url, function (response, status, xhr) {
        $('#form_update_param').on("submit", preventFormDefaultBehaviourOnSubmit);
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        $('#submit_save_parameter').on("click", function () {
            var data = Object();
            if ($('#editor_detail').length != 0) {
                editor = ace.edit("editor_detail");
                data['parameter_value'] = editor.getSession().getValue();
                data['csrf_token'] = $('#csrf_token').val();
            } else {
                data = $('#form_update_param').serializeObject();
                if ($('#parameter_value').attr('type') == "checkbox") {
                    data['parameter_value'] = $('#parameter_value').prop('checked');
                }
            }

            post_request_api('modules/set-parameter/' + decodeURIComponent(escape(window.btoa(param_name))), JSON.stringify(data))
            .done((data) => {
                if(notify_auto_api(data)) {
                    module_detail(module_id);
                    refresh_modules(true);
                    $('#modal_update_param').modal('hide');
                }
            })

            return false;
        })
    });
    $('#modal_update_param').modal({ show: true });
}

/* Fetch the details of an module and allow modification */
function module_detail(module_id) {
    url = 'modules/update/' + module_id + '/modal' + case_param();
    $('#modal_add_module_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_module').on("click", function () {
            post_request_api('modules/update/' + module_id, $('#form_new_module').serializeArray())
            .done((data) => {
                if(notify_auto_api(data)) {
                    module_detail(module_id);
                    $('#modal_update_param').modal('hide');
                }
            });

            return false;
        })

    });
    $('#modal_add_module').modal({ show: true });
}

function remove_module(id) {

    swal({
      title: "Are you sure?",
      text: "Please note this will only remove the reference of the module in Iris. The module will stay installed on the server.",
      icon: "warning",
      buttons: true,
      dangerMode: true,
      confirmButtonColor: '#3085d6',
      cancelButtonColor: '#d33',
      confirmButtonText: 'Yes, remove it!'
    })
    .then((willDelete) => {
      if (willDelete) {
        post_request_api('/manage/modules/remove/' + id)
        .done((data) => {
            if(notify_auto_api(data)) {
              refresh_modules(true);
              refresh_modules_hooks(true);
              $('#modal_add_module').modal('hide');
            }
        });
      } else {
        swal("Pfew, that was close");
      }
    });
}

function enable_module(module_id) {
    post_request_api('modules/enable/' + module_id)
    .done((data) => {
        if(notify_auto_api(data)) {
            refresh_modules(true);
            refresh_modules_hooks(true);
            module_detail(module_id);
        }
    });
}

function disable_module(module_id) {
    post_request_api('modules/disable/' + module_id)
    .done((data) => {
        if(notify_auto_api(data)) {
            refresh_modules(true);
            refresh_modules_hooks(true);
            module_detail(module_id);
        }
    });
}

