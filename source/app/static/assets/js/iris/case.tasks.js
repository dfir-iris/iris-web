
/* add filtering fields for each table of the page (must be done before datatable initialization) */
$.each($.find("table"), function(index, element){
    addFilterFields($(element).attr("id"));
});

Table = $("#tasks_table").DataTable({
    dom: 'Blfrtip',
    aaData: [],
    aoColumns: [
      {
        "data": "task_title",
        "render": function (data, type, row, meta) {
          if (type === 'display') {
            if (isWhiteSpace(data)) {
                data = '#' + row['task_id'];
            }
            data = '<a href="#" onclick="edit_task(\'' + row['task_id'] + '\');">' + data +'</a>';
          }
          return data;
        }
      },
      { "data": "task_description",
       "render": function (data, type, row, meta) {
          if (type === 'display') {
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
            } else {
                flag = 'muted';
            }
              data = '<span class="badge ml-2 badge-'+ flag +'">' + data + '</span>';
          }
          return data;
        }
      },
      {
        "data": "user_name"
      },
      {
        "data": "task_open_date"
      },
      { "data": "task_tags",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
              tags = "";
              de = data.split(',');
              for (tag in de) {
                tags += '<span class="badge badge-primary ml-2">' + de[tag] + '</span>';
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
        nRow = '<span class="badge ml-2 badge-'+ flag +'">' + data + '</span>';
    },
    filter: true,
    info: true,
    ordering: true,
    processing: true,
    retrieve: true,
    pageLength: 50,
    order: [[ 2, "desc" ]],
    buttons: [
    ],
    orderCellsTop: true,
    initComplete: function () {
        tableFiltering(this.api());
    }
});
$("#tasks_table").css("font-size", 12);
var buttons = new $.fn.dataTable.Buttons(Table, {
     buttons: [
        { "extend": 'csvHtml5', "text":'<i class="fas fa-cloud-download-alt"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Download as CSV' },
        { "extend": 'copyHtml5', "text":'<i class="fas fa-copy"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Copy' },
    ]
}).container().appendTo($('#tables_button'));

/* Fetch a modal that allows to add an event */
function add_task() {
    url = 'tasks/add/modal' + case_param();
    $('#modal_add_task_content').load(url, function () {
        $('#submit_new_task').on("click", function () {

            clear_api_error();
            if(!$('form#form_new_task').valid()) {
                return false;
            }

            var data_sent = $('#form_new_task').serializeObject();
            data_sent['task_tags'] = $('#task_tags').val();
            data_sent['task_assignee'] = $('#task_assignee').val();
            data_sent['task_status'] = $('#task_status').val();

            $.ajax({
                url: 'tasks/add' + case_param(),
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
                            get_tasks();
                            $('#modal_add_task').modal('hide');

                        });
                    } else {
                        $('#submit_new_task').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    $('#submit_new_task').text('Save');
                    propagate_form_api_errors(error.responseJSON.data);
                }
            });
        
            return false;
        })

    });
   
    $('#modal_add_task').modal({ show: true });
}

function update_task(id) {

    clear_api_error();
    if(!$('form#form_new_task').valid()) {
        return false;
    }

    var data_sent = $('#form_new_task').serializeObject();
    data_sent['task_tags'] = $('#task_tags').val();
    data_sent['task_assignee'] = $('#task_assignee').val();
    data_sent['task_status'] = $('#task_status').val();

    $.ajax({
        url: 'tasks/update/' + id + case_param(),
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
                    get_tasks();
                    $('#modal_add_task').modal('hide');

                });
            } else {
                $('#submit_new_task').text('Save again');
                swal("Oh no !", data.message, "error");
            }
        },
        error: function (error) {
            $('#submit_new_task').text('Save');
            propagate_form_api_errors(error.responseJSON.data);
        }
    });
}

/* Delete an event from the timeline thank to its id */ 
function delete_task(id) {

    $.ajax({
        url: "tasks/delete/" + id + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                swal("Done !",
                        "Your task has been deleted successfully",
                            {
                                icon: "success",
                                timer: 500
                            }
                    );
                get_tasks();
                $('#modal_add_task').modal('hide');
            } else {
                swal("Oh no !", data.message, "error")
            }
        },
        error: function (error) {
            notify_error("Oh no !", error.statusText, "error")
        }
    });
}

/* Edit and event from the timeline thanks to its ID */
function edit_task(id) {
  url = '/case/tasks/'+ id + '/modal' + case_param();
  $('#modal_add_task_content').load(url, function(){
        $('#modal_add_task').modal({show:true});
  });
}

/* Fetch and draw the tasks */
function get_tasks() {
    $('#tasks_list').empty();
    show_loader();
    $.ajax({
        url: "tasks/list" +  case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                    Table.MakeCellsEditable("destroy");
                    tasks_list = data.data.tasks;
                    Table.clear();
                    Table.rows.add(tasks_list);
                    hide_loader();
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
                              { "value": "Done", "display": "Done" },
                              { "value": "Canceled", "display": "Canceled" }
                            ]
                          }
                        ]
                      });

                    Table.columns.adjust().draw();
                    $('[data-toggle="popover"]').popover();

                    set_last_state(data.data.state);
                    hide_loader();
                }

        },
        error: function (error) {
            notify_error(error.statusText);
        }
    });
    
}

function callBackEditTaskStatus(updatedCell, updatedRow, oldValue) {
  data_send = updatedRow.data();
  data_send['csrf_token'] = $('#csrf_token').val();
  tid = data_send['task_id'];
  $.ajax({
    url: "tasks/status/update/" + tid + case_param(),
    type: "POST",
    data: JSON.stringify(data_send),
    dataType: "json",
    contentType: "application/json;charset=UTF-8",
    success: function (response) {
      if (response.status == 'success') {
           notify_success("Changes saved");
      } else {
        notify_error('Error :' + response.message)
      }
    },
    error: function (jqXHR, textStatus, errorThrown) {
        notify_error('Error :' + textStatus)
    }
  });
}


/* Page is ready, fetch the assets of the case */
$(document).ready(function(){
    get_tasks();
    setInterval(function() { check_update('tasks/state'); }, 3000);
});
