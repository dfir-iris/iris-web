$('#form_new_asset').submit(function () {

    $.ajax({
        url: '/manage/assets/add' + case_param(),
        type: "POST",
        data:  $('form#form_new_asset').serializeArray(),
        dataType: "json",
        beforeSend: function() {
            $('#submit_new_asset').text('Saving..')
                .attr("disabled", true)
                .removeClass('bt-outline-success')
                .addClass('btn-success', 'text-dark');
        },
        complete : function() {
             $('#submit_new_asset')
                .attr("disabled", false)
                .addClass('bt-outline-success')
                .removeClass('btn-success', 'text-dark');
        },
        success: function (data) {
            if (data.status == 'success') {
                $('#submit_new_asset').text('Saved');


                swal ( "That's done !" ,
                "Your new asset is now available" ,
                "success",
                {
                     buttons: {
                         again: {
                             text: "Create an asset again",
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
                       window.location.replace("/manage/assets" + case_param());
                       break;

                     default:
                      window.location.replace("/manage/assets" + case_param());
                   }
             });
            } else {
                $('#submit_new_asset').text('Save');
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
            $('#submit_new_asset').text('Save');
            notify_error(error);
        }
    });
    return false;
});


function add_report_template() {
    url = 'templates/add' + case_param();
    $('#modal_report_template_content').load(url, function () {

        /* create the select picker for language  */
        $('#report_language').selectpicker({
            liveSearch: true,
            title: "Language",
            style: "Bootstrap 4: 'btn-outline-primary'"
        });
        $('#report_type').selectpicker({
            liveSearch: true,
            title: "Report type",
            style: "Bootstrap 4: 'btn-outline-primary'"
        });
        $('#form_new_report_template').submit("click", function (event) {

            event.preventDefault();
            var formData = new FormData(this);

            $.ajax({
                url: url,
                type: "POST",
                data: formData,
                cache: false,
                contentType: false,
                processData: false,
                success: function (data) {
                    if (data.status == 'success') {
                        swal("Done !",
                        "Your report template has been created successfully",
                            {
                                icon: "success",
                                timer: 400
                            }
                        ).then((value) => {
                            refresh_template_table();
                            $('#modal_add_report_template').modal('hide');

                        });
                    } else {
                        $('#modal_add_report_template').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    $('#modal_add_report_template').text('Save');
                    swal("Oh no !", error.statusText, "error")
                }
            });

            return false;
        })
    });
    $('#modal_add_report_template').modal({ show: true });
}

$('#reports_table').dataTable( {
    "ajax": {
      "url": "templates/list" + case_param(),
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
    "autoWidth": false,
    "columns": [
        {
            "data": "name",
            "render": function ( data, type, row ) {
                data = sanitizeHTML(data);
                return '<a href="#" onclick="delete_report(\'' + row['id'] + '\');">' + data +'</a>';
            }
        },
        {
            "render": function ( data, type, row ) {return sanitizeHTML(data);},
             "data": "description",
        },
        {
            "render": function ( data, type, row ) {return sanitizeHTML(data);},
            "data": "naming_format",
        },
        {
            "render": function ( data, type, row ) {return sanitizeHTML(data);},
            "data": "date_created",
        },
        {
            "render": function ( data, type, row ) {return sanitizeHTML(data);},
            "data": "created_by",
        },
        {
            "render": function ( data, type, row ) {return sanitizeHTML(data);},
            "data": "code",
        },
        {
            "render": function ( data, type, row ) {return sanitizeHTML(data);},
            "data": "type_name",
        },
        {
            "render": function ( data, type, row ) {
                data = sanitizeHTML(data);
                return '<a href="templates/download/' + row["id"] + case_param() + '"><i class="fas fa-download"></i></a>';
            },
            "data": "id",
        }
      ]
    }
);

function refresh_template_table() {
  $('#reports_table').DataTable().ajax.reload();
  notify_success("Refreshed");
}


/* Fetch the details of an asset and allow modification */
function report_detail(report_id) {
    url = 'templates/update/' + report_id + case_param();
    $('#modal_report_template_content').load(url, function () {

        $('#submit_new_report_template').on("click", function () {
            $.ajax({
                url: url,
                type: "POST",
                data: $('#form_new_report_template').serializeArray(),
                dataType: "json",
                success: function (data) {
                    if (data.status == 'success') {
                        swal("You're set !",
                            "The report has been updated successfully",
                            {
                                icon: "success",
                                timer: 400
                            }
                        ).then((value) => {
                            refresh_template_table();
                            $('#modal_report_template').modal('hide');
                        });

                    } else {
                        $('#modal_report_template').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    notify_error(error.responseJSON.message);
                    propagate_form_api_errors(data.data);
                }
            });

            return false;
        })


    });
    $('#modal_report_template').modal({ show: true });
}

function delete_report(id) {

    swal({
      title: "This will delete the report template\nAre you sure?",
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
              url: '/manage/templates/delete/' + id + case_param(),
              type: "GET",
              dataType: 'JSON',
              success: function (data) {
                  if (data.status == 'success') {
                      swal("Template deleted !", {
                          icon: "success",
                          timer: 400
                      }).then((value) => {
                          refresh_template_table();
                          $('#modal_add_type').modal('hide');
                      });
                  } else {
                      swal ( "Oh no !" ,  data.message ,  "error" );
                  }
              },
              error: function (error) {
                notify_error(error.responseJSON.message);
                propagate_form_api_errors(data.data);
              }
          });
      } else {
        swal("Pfew, that's was close");
      }
    });
}