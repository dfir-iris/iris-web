$('#form_new_customer').submit(function () {
    event.preventDefault();
    $.ajax({
        url: '/manage/customers/add' + case_param(),
        type: "POST",
        data: JSON.stringify($('form#form_new_customer').serializeObject()),
        contentType: "application/json;charset=UTF-8",
        dataType: "json",
        success: function (data) {
            jsdata = data;
            if (jsdata.status == "success") {
                $('#modal_add_customer').modal('hide');
                notify_success(jsdata.message);
            } else {
                $('#modal_customer_message').text(jsdata.message);
            }
        },
        error: function (error) {
            propagate_form_api_errors(error.responseJSON.data);
        }
    });
});


$(document).ready(function() {
    update_tasks_list();
    update_gtasks_list();
    update_utasks_list();
    setInterval(check_page_update,30000);
});

function check_page_update(){
    update_tasks_list();
    update_gtasks_list();
    update_utasks_list();
}

function update_tasks_list() {
    $(this).toggleClass("down");
    $.ajax({
        url: '/tasks' + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
            jsdata = data;
            if (jsdata.status == "success") {
                content = jsdata.data;
                $("#task_feed").empty();
                for (index in content) {
                    if(content[index].state == 'progress') {
                        item_cat = "warning";
                    } else if(content[index].state == 'success') {
                            item_cat = "success";
                    } else {
                            item_cat = "danger";
                    }

                    $("#task_feed").append("<li class='feed-item feed-item-" + item_cat + "'>" +
                        "<time class='date' datetime='9-25'>" + content[index].date + "</time>" +
                        "<span class='text'>"+ content[index].human_data + " - <a href='#' onclick=\"task_status('"+ content[index].task_id +"');\">Details</a></span>" +
                        "</li>"
                    )
                }
                $('#feed_last_updated').text("Last updated: " + new Date().toLocaleTimeString());
            } else {
                $('#modal_customer_message').text(jsdata.message);
            }
        },
        error: function (error) {
            notify_error(error);
        }
    });
}

function task_status(id) {
    url = 'tasks/status/human/'+id + case_param();
    $('#info_task_modal_body').load(url, function(){
        $('#modal_task_detail').modal({show:true});
    });
}

UserTaskTable = $("#utasks_table").DataTable({
    dom: 'Blfrtip',
    aaData: [],
    aoColumns: [
      {
        "data": "task_title",
        "render": function (data, type, row, meta) {
          if (type === 'display') {
            if (isWhiteSpace(data)) {
                data = '#' + row['task_id'];
            } else {
                data = sanitizeHTML(data);
            }
            data = '<a href="case/tasks?cid='+ row['case_id'] + '&shared=' + row['task_id'] + '">' + data +'</a>';
          }
          return data;
        }
      },
      { "data": "task_description",
       "render": function (data, type, row, meta) {
          if (type === 'display') {
            data = sanitizeHTML(data);
            datas = '<span data-toggle="popover" style="cursor: pointer;" title="Info" data-trigger="click" href="#" data-content="' + data + '">' + data.slice(0, 70);

            if (data.length > 70) {
                datas += ' (..)</span>';
            } else {
                datas += '</span>';
            }
            return datas;
          }
          return data;
        }
      },
      {
        "data": "task_status_id",
        "render": function(data, type, row, meta) {
           if (type === 'display') {
              data = sanitizeHTML(data);
              data = '<span class="badge ml-2 badge-'+ row['status_bscolor'] +'">' + row['status_name'] + '</span>';
          }
          return data;
        }
      },
      {
        "data": "task_case",
        "render": function (data, type, row, meta) {
            if (type === 'display') {
                data = sanitizeHTML(data);
                data = '<a href="/case?cid='+ row['case_id'] +'">' + data +'</a>';
            }
            return data;
          }
      },
      {
        "data": "task_last_update",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
              data = sanitizeHTML(data);
              data = data.replace(/GMT/g, "");
          }
          return data;
        }
      },
      { "data": "task_tags",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
              tags = "";
              de = data.split(',');
              for (tag in de) {
                tags += '<span class="badge badge-primary ml-2">' + sanitizeHTML(de[tag]) + '</span>';
              }
              return tags;
          }
          return data;
        }
      }
    ],
    rowCallback: function (nRow, data) {
        data = sanitizeHTML(data);
        nRow = '<span class="badge ml-2 badge-'+ sanitizeHTML(data['status_bscolor']) +'">' + sanitizeHTML(data['status_name']) + '</span>';
    },
    filter: true,
    info: true,
    ordering: true,
    processing: true,
    retrieve: true,
    lengthChange: false,
    pageLength: 10,
    order: [[ 2, "desc" ]],
    buttons: [
        { "extend": 'csvHtml5', "text":'Export',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
        { "extend": 'copyHtml5', "text":'Copy',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
    ]
});
$("#utasks_table").css("font-size", 12);

function update_utasks_list() {
    $('#utasks_list').empty();
    $.ajax({
        url: "/user/tasks/list" + case_param(),
        type: "GET",
        success: function (data) {
            if (data.status == 'success') {
                    UserTaskTable.MakeCellsEditable("destroy");
                    tasks_list = data.data.tasks;

                    $('#user_attr_count').text(tasks_list.length);
                    if (tasks_list.length != 0){
                        $('#icon_user_task').removeClass().addClass('flaticon-alarm text-danger');
                    } else {
                        $('#icon_user_task').removeClass().addClass('flaticon-success text-success');
                    }
                    options_l = data.data.tasks_status;
                    options = [];
                    for (index in options_l) {
                        option = options_l[index];
                        options.push({ "value": option.id, "display": option.status_name })
                    }

                    UserTaskTable.clear();
                    UserTaskTable.rows.add(tasks_list);
                    UserTaskTable.MakeCellsEditable({
                        "onUpdate": callBackEditUserTaskStatus,
                        "inputCss": 'form-control col-12',
                        "columns": [2],
                        "allowNulls": {
                          "columns": [2],
                          "errorClass": 'error'
                        },
                        "confirmationButton": {
                          "confirmCss": 'my-confirm-class',
                          "cancelCss": 'my-cancel-class'
                        },
                        "inputTypes": [
                          {
                            "column": 2,
                            "type": "list",
                            "options": options
                          }
                        ]
                      });

                    UserTaskTable.columns.adjust().draw();
                    UserTaskTable.buttons().container().appendTo($('#utasks_table_info'));
                       $('[data-toggle="popover"]').popover();
                    $('#utasks_last_updated').text("Last updated: " + new Date().toLocaleTimeString());
                }

        },
        error: function (error) {
            notify_error(error);
        }
    });

}

function callBackEditUserTaskStatus(updatedCell, updatedRow, oldValue) {
  data_send = updatedRow.data()
  data_send['csrf_token'] = $('#csrf_token').val();
  $.ajax({
    url: "user/tasks/status/update" + case_param(),
    type: "POST",
    data: JSON.stringify(data_send),
    contentType: "application/json;charset=UTF-8",
    dataType: 'json',
    success: function (response) {
      if (response.status == 'success') {
           notify_success("Changes saved");
           update_utasks_list();
           UserTaskTable.columns.adjust().draw();
      } else {
        notify_error('Error :' + response.message)
      }
    },
    error: function (error) {
        notify_error(error);
    }
  });
}


/**** GTASKS ****/
Table = $("#gtasks_table").DataTable({
    dom: 'Blfrtip',
    aaData: [],
    aoColumns: [
      {
        "data": "task_title",
        "render": function (data, type, row, meta) {
          if (type === 'display') {
            if (isWhiteSpace(data)) {
                data = '#' + row['task_id'];
            } else {
                data = sanitizeHTML(data);
            }
            data = '<a href="#" onclick="edit_gtask(\'' + row['task_id'] + '\');">' + data +'</a>';
          }
          return data;
        }
      },
      { "data": "task_description",
       "render": function (data, type, row, meta) {
          if (type === 'display') {
            data = sanitizeHTML(data);
            datas = '<span data-toggle="popover" style="cursor: pointer;" title="Info" data-trigger="click" href="#" data-content="' + data + '">' + data.slice(0, 70);

            if (data.length > 70) {
                datas += ' (..)</span>';
            } else {
                datas += '</span>';
            }
            return datas;
          }
          return data;
        }
      },
      {
        "data": "task_status_id",
        "render": function(data, type, row, meta) {
            if (type === 'display' && data != null) {
                data = sanitizeHTML(data);
                data = '<span class="badge ml-2 badge-'+ row['status_bscolor'] +'">' + row['status_name'] + '</span>';
            }
          return data;
        }
      },
      {
        "data": "user_name",
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
      },
      {
        "data": "task_last_update",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
              data = sanitizeHTML(data);
              data = data.replace(/GMT/g, "");
          }
          return data;
        }
      },
      { "data": "task_tags",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
              tags = "";
              de = data.split(',');
              for (tag in de) {
                tags += '<span class="badge badge-primary ml-2">' + sanitizeHTML(de[tag]) + '</span>';
              }
              return tags;
          }
          return data;
        }
      }
    ],
    rowCallback: function (nRow, data) {
        nRow = '<span class="badge ml-2 badge-'+ sanitizeHTML(data['status_bscolor']) +'">' + sanitizeHTML(data['status_name']) + '</span>';
    },
    filter: true,
    info: true,
    ordering: true,
    processing: true,
    retrieve: true,
    lengthChange: false,
    pageLength: 10,
    order: [[ 2, "desc" ]],
    buttons: [
        { "extend": 'csvHtml5', "text":'Export',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
        { "extend": 'copyHtml5', "text":'Copy',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
    ]
});
$("#gtasks_table").css("font-size", 12);

/* Fetch a modal that allows to add an event */
function add_gtask() {
    url = '/global/tasks/add' + case_param();
    $('#modal_add_gtask_content').load(url, function () {
        $('#submit_new_gtask').on("click", function () {
            var data_sent = $('#form_new_gtask').serializeObject();
            data_sent['task_tags'] = $('#task_tags').val();
            data_sent['task_assignee'] = $('#task_assignee').val();
            data_sent['task_status_id'] = $('#task_status_id').val();
            data_sent['csrf_token'] = $('#csrf_token').val();

            $.ajax({
                url: url,
                type: "POST",
                data: JSON.stringify(data_sent),
                contentType: "application/json;charset=UTF-8",
                dataType: "json",
                success: function (data) {
                    if (data.status == 'success') {
                        swal("Done !",
                        "Your task has been created successfully",
                            {
                                icon: "success",
                                timer: 500
                            }
                        ).then((value) => {
                            update_gtasks_list();
                            $('#modal_add_gtask').modal('hide');

                        });
                    } else {
                        $('#submit_new_gtask').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    $('#submit_new_gtask').text('Save');
                    propagate_form_api_errors(error.responseJSON.data);
                }
            });

            return false;
        })

    });

    $('#modal_add_gtask').modal({ show: true });
}

function update_gtask(id) {
    var data_sent = $('#form_new_gtask').serializeObject();
    data_sent['task_tags'] = $('#task_tags').val();
    data_sent['task_assignee'] = $('#task_assignee').val();
    data_sent['task_status_id'] = $('#task_status_id').val();
    data_sent['csrf_token'] = $('#csrf_token').val();

    $.ajax({
        url: '/global/tasks/udpate/' + id + case_param(),
        type: "POST",
        data: JSON.stringify(data_sent),
        dataType: "json",
        contentType: "application/json;charset=UTF-8",
        success: function (data) {
            if (data.status == 'success') {
                swal("Done !",
                "Updated successfully",
                    {
                        icon: "success",
                        timer: 500
                    }
                ).then((value) => {
                    update_gtasks_list();
                    $('#modal_add_gtask').modal('hide');

                });
            } else {
                $('#submit_new_gtask').text('Save again');
                propagate_form_api_errors(data.data);
            }
        },
        error: function (error) {
            $('#submit_new_gtask').text('Save');
            propagate_form_api_errors(error.responseJSON.data);
        }
    });
}

/* Delete an event from the timeline thank to its id */
function delete_gtask(id) {

    $.ajax({
        url: "/global/tasks/delete/" + id + case_param(),
        type: "GET",
        success: function (data) {
            if (data.status == 'success') {
                swal("Done !",
                        "Task has been deleted successfully",
                            {
                                icon: "success",
                                timer: 500
                            }
                    );
                update_gtasks_list();
                $('#modal_add_gtask').modal('hide');
            } else {
                swal("Oh no !", data.message, "error")
            }
        },
        error: function (error) {
            swal("Oh no !", error.responseJSON.message, "error")
        }
    });
}

/* Edit and event from the timeline thanks to its ID */
function edit_gtask(id) {
  url = '/global/tasks/update/'+ id + case_param();
  $('#modal_add_gtask_content').load(url, function(){
        $('#modal_add_gtask').modal({show:true});
  });
}

/* Fetch and draw the tasks */
function update_gtasks_list() {
    $('#gtasks_list').empty();
    $.ajax({
        url: "/global/tasks/list" + case_param(),
        type: "GET",
        success: function (data) {
            if (data.status == 'success') {
                    Table.MakeCellsEditable("destroy");
                    tasks_list = data.data.tasks;

                    options_l = data.data.tasks_status;
                    options = [];
                    for (index in options_l) {
                        option = options_l[index];
                        options.push({ "value": option.id, "display": option.status_name })
                    }

                    Table.clear();
                    Table.rows.add(tasks_list);

                    Table.columns.adjust().draw();
                    Table.buttons().container().appendTo($('#gtasks_table_info'));
                       $('[data-toggle="popover"]').popover();
                    $('#tasks_last_updated').text("Last updated: " + new Date().toLocaleTimeString());
                }

        },
        error: function (error) {

        }
    });

}
