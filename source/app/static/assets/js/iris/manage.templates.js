function add_report_template() {
    url = 'templates/add/modal' + case_param();
    $('#modal_report_template_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

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
                url: 'templates/add' + case_param(),
                type: "POST",
                data: formData,
                cache: false,
                contentType: false,
                processData: false,
                success: function (data) {
                    if (notify_auto_api(data)) {
                        refresh_template_table();
                        $('#modal_add_report_template').modal('hide');
                    }
                },
                error: function (error) {
                    if(error.responseJSON) {
                        notify_error(error.responseJSON.message);
                    } else {
                        ajax_notify_error(error, this.url);
                    }
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
    $('#modal_report_template_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_report_template').on("click", function () {
            $.ajax({
                url: url,
                type: "POST",
                data: $('#form_new_report_template').serializeArray(),
                dataType: "json",
                success: function (data) {
                    if (notify_auto_api(data)) {
                        refresh_template_table();
                        $('#modal_add_report_template').modal('hide');
                    }
                },
                error: function (error) {
                    if(error.responseJSON) {
                        notify_error(error.responseJSON.message);
                    } else {
                        ajax_notify_error(error, this.url);
                    }
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
          post_request_api('/manage/templates/delete/' + id)
          .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_template_table();
                    $('#modal_add_report_template').modal('hide');
                }
          });
      } else {
        swal("Pfew, that was close");
      }
    });
}