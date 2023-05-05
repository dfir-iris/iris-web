function add_case_template() {
    let url = '/manage/case-templates/add/modal' + case_param();
    $('#modal_case_template_json').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        let editor = ace.edit("editor_detail",
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
                {value: 'name', score: 1, meta: 'name of the template'},
                {value: 'display', score: 1, meta: 'display name of the template'},
                {value: 'description', score: 1, meta: 'description of the template'},
                {value: 'author', score: 1, meta: 'author of the template'},
                {value: 'title_prefix', score: 1, meta: 'prefix of instantiated cases'},
                {value: 'summary', score: 1, meta: 'summary of the case'},
                {value: 'tags', score: 1, meta: 'tags of the case or the tasks'},
                {value: 'tasks', score: 1, meta: 'tasks of the case'},
                {value: 'note_groups', score: 1, meta: 'groups of notes'},
                {value: 'title', score: 1, meta: 'title of the task or the note group or the note'},
                {value: 'content', score: 1, meta: 'content of the note'},
              ]);
            },
          }],
          enableLiveAutocompletion: true,
          enableSnippets: true
        });

        $('#submit_new_case_template').on("click", function () {
            let data_sent = Object();
            data_sent['case_template_json'] = editor.getSession().getValue();
            data_sent['csrf_token'] = $("#csrf_token").val();

            post_request_api('/manage/case-templates/add', JSON.stringify(data_sent), false, function() {
                window.swal({
                      title: "Adding...",
                      text: "Please wait",
                      icon: "/static/assets/img/loader.gif",
                      button: false,
                      allowOutsideClick: false
                });
            })
            .done((data) => {
                if (notify_auto_api(data)) {
                    refresh_case_template_table();
                    $('#modal_case_template').modal('hide');
                }
            })
            .fail((error) => {
                let data = error.responseJSON;
                $('#submit_new_case_template').text('Save');
                $('#alert_case_template_edit').text(data.message);
                if (data.data && data.data.length > 0) {

                    let output='<li>'+ sanitizeHTML(data.data) +'</li>';
                    $('#case_template_err_details_list').append(output);

                    $('#alert_case_template_details').show();
                }
                $('#alert_case_template_edit').show();
            })
            .always((data) => {
                window.swal.close();
            });

            return false;
        })
    });
    $('#modal_case_template').modal({ show: true });
}

$('#case_templates_table').dataTable( {
    "ajax": {
      "url": "/manage/case-templates/list" + case_param(),
      "contentType": "application/json",
      "type": "GET",
      "data": function ( d ) {
        if (d.status == 'success') {
          return JSON.stringify( d.data );
        } else {
          return JSON.stringify([]);
        }
      }
    },
    "order": [[ 0, "desc" ]],
    "autoWidth": false,
    "columns": [
            {
                "data": "id",
                "render": function ( data, type, row ) {
                    return '<a href="#" onclick="case_template_detail(\'' + row['id'] + '\');">' + sanitizeHTML(data) +'</a>';
                }
            },
            {
                "data": "display_name",
                "render": function ( data, type, row ) {
                    return '<a href="#" onclick="case_template_detail(\'' + row['id'] + '\');">' + sanitizeHTML(data) +'</a>';
                }
            },
            {
                "data": "description"
            },
            {
                "data": "added_by"
            },
            {
                "data": "created_at"
            },
            {
                "data": "updated_at"
            }

        ]
    }
);

function refresh_case_template_table() {
  $('#case_templates_table').DataTable().ajax.reload();
  notify_success("Refreshed");
}

function delete_case_template(id) {
    swal({
        title: "Are you sure ?",
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
            post_request_api('/manage/case-templates/delete/' + id)
            .done((data) => {
                if(notify_auto_api(data)) {
                    window.location.href = '/manage/case-templates' + case_param();
                }
            });
        } else {
            swal("Pfew, that was close");
        }
    });
}

function case_template_detail(ctempl_id) {
    let url = '/manage/case-templates/' + ctempl_id + '/modal' + case_param();
    $('#modal_case_template_json').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        let editor = ace.edit("editor_detail",
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
                {value: 'name', score: 1, meta: 'name of the template'},
                {value: 'display_name', score: 1, meta: 'display name of the template'},
                {value: 'description', score: 1, meta: 'description of the template'},
                {value: 'author', score: 1, meta: 'author of the template'},
                {value: 'title_prefix', score: 1, meta: 'prefix of instantiated cases'},
                {value: 'summary', score: 1, meta: 'summary of the case'},
                {value: 'tags', score: 1, meta: 'tags of the case or the tasks'},
                {value: 'tasks', score: 1, meta: 'tasks of the case'},
                {value: 'note_groups', score: 1, meta: 'groups of notes'},
                {value: 'title', score: 1, meta: 'title of the task or the note group or the note'},
                {value: 'content', score: 1, meta: 'content of the note'},
              ]);
            },
          }],
          enableLiveAutocompletion: true,
          enableSnippets: true
        });

        $('#submit_new_case_template').on("click", function () {
            update_case_template(ctempl_id, editor, false, false);
        });

        $('#submit_delete_case_template').on("click", function () {
            delete_case_template(ctempl_id);
        });
    });
    $('#modal_case_template').modal({ show: true });
}

function update_case_template(ctempl_id, editor, partial, complete){
    event.preventDefault();

    let data_sent = Object();
    data_sent['case_template_json'] = editor.getSession().getValue();
    data_sent['csrf_token'] = $("#csrf_token").val();

    $('#alert_case_template_edit').empty();
    $('#alert_case_template_details').hide();
    $('#case_template_err_details_list').empty();

    post_request_api('/manage/case-templates/update/' + ctempl_id, JSON.stringify(data_sent), false, function() {
        window.swal({
              title: "Updating...",
              text: "Please wait",
              icon: "/static/assets/img/loader.gif",
              button: false,
              allowOutsideClick: false
        });
    })
    .done((data) => {
        notify_auto_api(data);
    })
    .fail((error) => {
        let data = error.responseJSON;
        $('#submit_new_case_template').text('Update');
        $('#alert_case_template_edit').text(data.message);
        if (data.data && data.data.length > 0) {
            let output='<li>'+ sanitizeHTML(data.data) +'</li>';
            $('#case_template_err_details_list').append(output);

            $('#alert_case_template_details').show();
        }
        $('#alert_case_template_edit').show();
    })
    .always((data) => {
        window.swal.close();
    });

    return false;
}

function fire_upload_case_template() {
    let url = '/manage/case-templates/upload/modal' + case_param();
    $('#modal_upload_case_template_json').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
    });
    $('#modal_upload_case_template').modal({ show: true });
}

function upload_case_template() {

    if ($("#input_upload_case_template").val() !== "")
    {
        var file = $("#input_upload_case_template").get(0).files[0];
        var reader = new FileReader();
        reader.onload = function (e) {
            fileData = e.target.result
            var data = new Object();
            data['csrf_token'] = $('#csrf_token').val();
            data['case_template_json'] = fileData;

            post_request_api('/manage/case-templates/add', JSON.stringify(data), false, function() {
                window.swal({
                      title: "Adding...",
                      text: "Please wait",
                      icon: "/static/assets/img/loader.gif",
                      button: false,
                      allowOutsideClick: false
                });
            })
           .done((data) => {
                notify_auto_api(data);
                jsdata = data;
                if (jsdata.status == "success") {
                    refresh_case_template_table();
                    $('#modal_upload_case_template').modal('hide');
                }
           })
           .fail((error) => {
                let data = error.responseJSON;
                $('#alert_upload_case_template').text(data.message);
                if (data.data && data.data.length > 0) {

                    let output='<li>'+ sanitizeHTML(data.data) +'</li>';
                    $('#upload_case_template_err_details_list').append(output);

                    $('#alert_upload_case_template_details').show();
                }
                $('#alert_upload_case_template').show();
            })
            .always((data) => {
                $("#input_upload_case_template").val("");
                window.swal.close();
            });

        };
        reader.readAsText(file);
    }


    return false;
}

function downloadCaseTemplateDefinition() {
    event.preventDefault();
    let editor = ace.edit("editor_detail");
    let data = editor.getSession().getValue();

    let filename = "case_template.json";
    download_file(filename, 'text/json' , data);
}