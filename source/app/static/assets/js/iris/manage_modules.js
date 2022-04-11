$('#form_new_module').submit(function () {

    $.ajax({
        url: '/manage/modules/add' + case_param(),
        type: "POST",
        data:  $('form#form_new_module').serializeArray(),
        dataType: "json",
        beforeSend: function() {
            $('#submit_new_module').text('Saving..')
                .attr("disabled", true)
                .removeClass('bt-outline-success')
                .addClass('btn-success', 'text-dark');
        },
        complete : function() {
             $('#submit_new_module')
                .attr("disabled", false)
                .addClass('bt-outline-success')
                .removeClass('btn-success', 'text-dark');
        },
        success: function (data) {
            if (data.status == 'success') {
                $('#submit_new_module').text('Saved');


                swal ( "That's done !" ,
                "Your new module is now available" ,
                "success",
                {
                     buttons: {
                         again: {
                             text: "Create an module again",
                             value: "again"
                         },
                         case: {
                           text: "Go to case",
                           value: "case",
                         }
                     }
                 }
                ).then((value) => {
                   switch (value) {

                     case "case":
                       window.location.replace("/case/summary" + case_param());
                       break;

                     case "again":
                       window.location.replace("/manage/modules" + case_param());
                       break;

                     default:
                      window.location.replace("/manage/modules" + case_param());
                   }
             });
            } else {
                $('#submit_new_module').text('Save');
                mdata = ""
                for (element in data.data) {
                    mdata += data.data[element]
                }
                $.notify({
                    icon: 'flaticon-error',
                    title: data.message,
                    message: mdata
                }, {
                    type: 'danger',
                    placement: {
                        from: 'top',
                        align: 'right'
                    },
                    time: 5000,
                });
                }
            },
        error: function (error) {
            $('#submit_new_module').text('Save');
            notify_error(error);
        }
    });
    return false;
});


function add_module() {
    url = 'modules/add' + case_param();
    $('#modal_add_module_content').load(url, function () {

        $('#submit_new_module').on("click", function () {
            $.ajax({
                url: url,
                type: "POST",
                data: $('#form_new_module').serializeArray(),
                dataType: "json",
                send: function () {$('#submit_new_module').text("Testing module");},
                success: function (data) {
                    if (data.status == 'success') {
                        swal("Done !",
                        "Module has been imported successfully",
                            {
                                icon: "success",
                                timer: 500
                            }
                        ).then((value) => {
                            refresh_modules();
                            refresh_modules_hooks();
                            $('#modal_add_module').modal('hide');

                        });
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
                },
                error: function (error) {
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
                }
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

function refresh_modules() {
  $('#modules_table').DataTable().ajax.reload();
  $(function () {
  $('[data-toggle="tooltip"]').tooltip()
})
  notify_success("Modules refreshed");
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

function refresh_modules_hooks() {
  $('#hooks_table').DataTable().ajax.reload();
  notify_success("Hooks refreshed");
}


function export_mod_config(module_id) {
    $.ajax({
          url: '/manage/modules/export-config/' + module_id + case_param(),
          type: "GET",
          dataType: 'JSON',
          success: function (data) {
              if (data.status == 'success') {
                    download_file(data.data.module_name + "_configuration_export.json", "text/json",
                    JSON.stringify(data.data.module_configuration, null, 4));
              } else {
                  swal ( "Oh no !" ,  data.message ,  "error" );
              }
          },
          error: function (error) {
              swal ( "Oh no !" ,  error ,  "error" );
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
        $.ajax({
            url: '/manage/modules/import-config/'+ module_id + case_param(),
            type: "POST",
            data: JSON.stringify(data),
            contentType: "application/json;charset=UTF-8",
            dataType: "json",
            success: function (data) {
                jsdata = data;
                if (jsdata.status == "success") {
                    module_detail(module_id);
                    $('#modal_input_config').modal('hide');
                    swal("Got news for you", data.message, "success");

                } else {
                    swal("Got bad news for you", data.data, "error");
                }
            },
            error: function (error) {
                notify_error(error.responseJSON.message);
                propagate_form_api_errors(error.responseJSON.data);
            }
        });
    };
    reader.readAsText(file)

    return false;
}

/* Update the param of a module */
function update_param(module_id, param_name) {
    url = 'modules/update_param/' + decodeURIComponent(escape(window.btoa(param_name))) + case_param();
    $('#modal_update_param_content').load(url, function () {
        $('#submit_save_parameter').on("click", function () {
            var data = Object();
            if ($('#editor_detail').length != 0) {
                editor = ace.edit("editor_detail");
                data['param_value'] = editor.getSession().getValue();
                data['csrf_token'] = $('#csrf_token').val();
            } else {
                data = $('#form_update_param').serializeObject();
                if ($('#param_value').attr('type') == "checkbox") {
                    data['param_value'] = $('#param_value').prop('checked');
                }
            }
            $.ajax({
                url: url,
                type: "POST",
                data: JSON.stringify(data),
                contentType: "application/json;charset=UTF-8",
                dataType: "json",
                success: function (data) {
                    if (data.status == 'success') {
                        swal("You're set !",
                            "Parameter updated successfully",
                            {
                                icon: "success",
                                timer: 500
                            }
                        ).then((value) => {
                            module_detail(module_id);
                            $('#modal_update_param').modal('hide');
                        });

                    } else {
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    swal("Oh no !", error.statusText, "error")
                }
            });

            return false;
        })
    });
    $('#modal_update_param').modal({ show: true });
}

/* Fetch the details of an module and allow modification */
function module_detail(module_id) {
    url = 'modules/update/' + module_id + case_param();
    $('#modal_add_module_content').load(url, function () {

        $('#submit_new_module').on("click", function () {
            $.ajax({
                url: url,
                type: "POST",
                data: $('#form_new_module').serializeArray(),
                dataType: "json",
                success: function (data) {
                    if (data.status == 'success') {
                        swal("You're set !",
                            "The module has been updated successfully",
                            {
                                icon: "success",
                                timer: 1500
                            }
                        ).then((value) => {
                            refresh_modules();
                            $('#modal_add_module').modal('hide');
                        });

                    } else {
                        $('#modal_add_module').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    swal("Oh no !", error.statusText, "error")
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
          $.ajax({
              url: '/manage/modules/remove/' + id + case_param(),
              type: "GET",
              dataType: 'JSON',
              success: function (data) {
                  if (data.status == 'success') {
                      swal("Module deleted !", {
                          icon: "success",
                          timer: 1000
                      }).then((value) => {
                          refresh_modules();
                          refresh_modules_hooks();
                          $('#modal_add_module').modal('hide');
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

function enable_module(module_id) {
    url = 'modules/enable/' + module_id + case_param();
    $.ajax({
        url: url,
        type: "GET",
        success: function (data) {
            if (data.status == 'success') {
                swal("Done !",
                "Module has been activated successfully",
                    {
                        icon: "success",
                        timer: 500
                    }
                ).then((value) => {
                    refresh_modules();
                    refresh_modules_hooks();
                    module_detail(module_id);
                });
            } else {
                swal("Oh no !", 'unexpected error', "error")
            }
        },
        error: function (error) {
            $('#submit_new_module').text('Save');
            swal("Oh no !", error.statusText, "error")
        }
    });
}

function disable_module(module_id) {
    url = 'modules/disable/' + module_id + case_param();
    $.ajax({
        url: url,
        type: "GET",
        success: function (data) {
            if (data.status == 'success') {
                swal("Done !",
                "Module has been disabled successfully",
                    {
                        icon: "success",
                        timer: 500
                    }
                ).then((value) => {
                    refresh_modules();
                    refresh_modules_hooks();
                    module_detail(module_id);
                });
            } else {
                swal("Oh no !", 'unexpected error', "error")
            }
        },
        error: function (error) {
            $('#submit_new_module').text('Save');
            swal("Oh no !", error.statusText, "error")
        }
    });
}

$('.modal').on('hidden.bs.modal', function (e) {
    $('body').addClass('modal-open');
});