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
            },
            {
                "data": "attribute_display_name",
                "render": function ( data, type, row ) {
                    return '<a href="#" onclick="attribute_detail(\'' + row['attribute_id'] + '\');">' + sanitizeHTML(data) +'</a>';
                }
            },
            {
                "data": "attribute_description"
            }
        ]
    }
);

function refresh_attribute_table() {
  $('#attributes_table').DataTable().ajax.reload();
  notify_success("Refreshed");
}

function attribute_detail(attr_id) {
    url = '/manage/attributes/' + attr_id + '/modal' + case_param();
    $('#modal_add_attribute_content').load(url, function () {

        var editor = ace.edit("editor_detail",
            {
                autoScrollEditorIntoView: true,
                minLines: 30,
            });
        editor.setTheme("ace/theme/tomorrow");
        editor.session.setMode("ace/mode/json");
        editor.renderer.setShowGutter(true);
        editor.setOption("showLineNumbers", true);
        editor.setOption("showPrintMargin", false);
        editor.setOption("displayIndentGuides", true);
        editor.setOption("maxLines", "Infinity");
        editor.session.setUseWrapMode(true);
        editor.setOption("indentedSoftWrap", true);
        editor.renderer.setScrollMargin(8, 5)

        editor.setOptions({
          enableBasicAutocompletion: [{
            getCompletions: (editor, session, pos, prefix, callback) => {
              callback(null, [
                {value: 'mandatory', score: 1, meta: 'mandatory tag'},
                {value: 'type', score: 1, meta: 'type tag'},
                {value: 'value', score: 1, meta: 'default value'},
              ]);
            },
          }],
          enableLiveAutocompletion: true,
          enableSnippets: true
        });

        $('#submit_new_attribute').on("click", function () {
            event.preventDefault();

            var data_sent = Object();
            data_sent['attribute_content'] = editor.getSession().getValue();
            data_sent['csrf_token'] = $("#csrf_token").val();

            $.ajax({
                url:  '/manage/attributes/update/' + attr_id + case_param(),
                type: "POST",
                data: JSON.stringify(data_sent),
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

