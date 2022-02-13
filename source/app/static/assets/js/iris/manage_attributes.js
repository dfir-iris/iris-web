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
                {value: 'input_string', score: 1, meta: 'An input string field type'},
                {value: 'input_checkbox', score: 1, meta: 'An input checkbox field type'},
                {value: 'input_textfield', score: 1, meta: 'An input textfield field type'},
                {value: 'raw', score: 1, meta: 'A raw field type'},
                {value: 'html', score: 1, meta: 'An html field type'},
                {value: 'value', score: 1, meta: 'default value'},
              ]);
            },
          }],
          enableLiveAutocompletion: true,
          enableSnippets: true
        });

        $('#preview_attribute').on("click", function () {
             var data_sent = Object();
            data_sent['attribute_content'] = editor.getSession().getValue();
            data_sent['csrf_token'] = $("#csrf_token").val();

            $.ajax({
                url: '/manage/attributes/preview' + case_param(),
                type: "POST",
                data: JSON.stringify(data_sent),
                dataType: "json",
                contentType: "application/json;charset=UTF-8",
                success: function(data) {
                    $('#modal_preview_attribute_content').html(data.data);

                    $('#modal_preview_attribute').modal({ show: true });
                },
                error:function(request, status, error) {
                    notify_error(request.responseText);
                }
            });
        });

        $('#submit_new_attribute').on("click", function () {
            update_attribute(attr_id, editor, false, false);
        })
        $('#submit_partial_overwrite').on("click", function () {
            update_attribute(attr_id, editor, true, false);
        })
        $('#submit_complete_overwrite').on("click", function () {
            update_attribute(attr_id, editor, false, true);
        })


    });
    $('#modal_add_attribute').modal({ show: true });
}

function update_attribute(attr_id, editor, partial, complete){
    event.preventDefault();

    var data_sent = Object();
    data_sent['attribute_content'] = editor.getSession().getValue();
    data_sent['csrf_token'] = $("#csrf_token").val();
    data_sent['partial_overwrite'] = partial;
    data_sent['complete_overwrite'] = complete;

    $('#alert_attributes_edit').empty();
    $('#alert_attributes_details').hide();
    $('#attributes_err_details_list').empty();

    $.ajax({
        url:  '/manage/attributes/update/' + attr_id + case_param(),
        type: "POST",
        data: JSON.stringify(data_sent),
        dataType: "json",
        contentType: "application/json;charset=UTF-8",
        beforeSend: function() {
            window.swal({
                  title: "Updating and migrating...",
                  text: "Please wait",
                  imageUrl: "images/ajaxloader.gif",
                  showConfirmButton: false,
                  allowOutsideClick: false
            });
        },
        complete: function() {
            window.swal.close();
        },
        success: function (data) {
            if (data.status == 'success') {
                notify_success(data.message);
            } else {
                $('#modal_add_attribute').text('Save again');
                swal("Oh no !", data.message, "error")
            }
        },
        error: function (error) {
            data = error.responseJSON;
            $('#submit_new_attribute').text('Save');
            $('#alert_attributes_edit').text(data.message);
            if (data.data && data.data.length > 0) {
                for(var i in data.data)
                {
                   var output='<li>'+data.data[i]+'</li>';
                   console.log(output);
                   $('#attributes_err_details_list').append(output);
                }

                $('#alert_attributes_details').show();
            }
            $('#alert_attributes_edit').show();
            $('#submit_new_module').text("Retry");
        }
    });

    return false;
}
