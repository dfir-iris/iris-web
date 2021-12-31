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
    setInterval(update_tasks_list,30000);
    setInterval(update_gtasks_list, 33000)
});

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
        "data": "task_status",
        "render": function(data, type, row, meta) {
           if (type === 'display') {
            if (row['task_status'] == 'To do') {
                flag = 'danger';
            } else if (row['task_status'] == 'In progress') {
                flag = 'warning';
            } else if (row['task_status'] == 'Done') {
                flag = 'success';
            } else if (row['task_status'] == 'On hold') {
                flag = 'dark';
            } else {
                flag = 'muted';
            }
            data = sanitizeHTML(data);
            data = '<span class="badge ml-2 badge-'+ flag +'">' + data + '</span>';
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
        if (data['task_status'] == 'To do') {
            flag = 'danger';
        } else if (data['task_status'] == 'In progress') {
            flag = 'warning';
        } else if (data['task_status'] == 'Done') {
            flag = 'success';
        } else {
            flag = 'muted';
        }
        data = sanitizeHTML(data);
        nRow = '<span class="badge ml-2 badge-'+ flag +'">' + data + '</span>';
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
            data_sent['task_status'] = $('#task_status').val();
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
    data_sent['task_status'] = $('#task_status').val();
    data_sent['csrf_token'] = $('#csrf_token').val();

    $.ajax({
        url: '/global/tasks/edit/' + id + case_param(),
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
  url = '/global/tasks/edit/'+ id + case_param();
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
                    tasks_list = data.data;
                    Table.clear();
                    Table.rows.add(tasks_list);
                    Table.MakeCellsEditable({
                        "onUpdate": callBackEditTaskStatus,
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
                            "options": [
                              { "value": "To do", "display": "To do" },
                              { "value": "In progress", "display": "In progress" },
                              { "value": "On hold", "display": "On hold" },
                              { "value": "Done", "display": "Done" },
                              { "value": "Canceled", "display": "Canceled" }
                            ]
                          }
                        ]
                      });

                    Table.columns.adjust().draw();
                    Table.buttons().container().appendTo($('#gtasks_table_info'));
                       $('[data-toggle="popover"]').popover();
                    $('#tasks_last_updated').text("Last updated: " + new Date().toLocaleTimeString());
                }

        },
        error: function (error) {
            notify_error(error.responseJSON.message);
        }
    });

}

function callBackEditTaskStatus(updatedCell, updatedRow, oldValue) {
  data_send = updatedRow.data()
  data_send['csrf_token'] = $('#csrf_token').val();
  $.ajax({
    url: "global/tasks/update-status" + case_param(),
    type: "POST",
    data: JSON.stringify(data_send),
    contentType: "application/json;charset=UTF-8",
    dataType: 'json',
    success: function (response) {
      if (response.status == 'success') {
           notify_success("Changes saved");
          Table.columns.draw();
      } else {
        notify_error('Error :' + response.message)
      }
    },
    error: function (error) {
        notify_error(error.responseJSON.message);
    }
  });
}
