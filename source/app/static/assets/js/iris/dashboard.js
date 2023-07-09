let UserReviewsTable;
let UserCasesTable;
let UserTaskTable;
function check_page_update(){
    update_gtasks_list();
    update_utasks_list();
}

function task_status(id) {
    url = 'tasks/status/human/'+id + case_param();
    $('#info_task_modal_body').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        $('#modal_task_detail').modal({show:true});
    });
}

async function update_ucases_list(show_all=false) {
    $('#ucases_list').empty();
    get_raw_request_api("/user/cases/list" + case_param() + "&show_closed=" + show_all)
    .done((data) => {
        if (notify_auto_api(data, true)) {
            UserCasesTable.clear();
            UserCasesTable.rows.add(data.data);
            UserCasesTable.columns.adjust().draw();
            UserCasesTable.buttons().container().appendTo($('#ucases_table_info'));
            $('[data-toggle="popover"]').popover();
            $('#ucases_last_updated').text("Last updated: " + new Date().toLocaleTimeString());
        }
    });
}

async function update_ureviews_list() {
    get_raw_request_api("/user/reviews/list" + case_param())
    .done((data) => {
        if (notify_auto_api(data, true)) {
            if (data.data.length == 0) {
                $('#rowPendingCasesReview').hide();
                return;
            }
            UserReviewsTable.clear();
            UserReviewsTable.rows.add(data.data);
            UserReviewsTable.columns.adjust().draw();
            $('[data-toggle="popover"]').popover();
            $('#ureviews_last_updated').text("Last updated: " + new Date().toLocaleTimeString());
            $('#rowPendingCasesReview').show();
        }
    });
}

async function update_utasks_list() {
    $('#utasks_list').empty();
    return get_request_api("/user/tasks/list")
    .done((data) => {
        if (notify_auto_api(data, true)) {
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

    });
}

function callBackEditUserTaskStatus(updatedCell, updatedRow, oldValue) {
    data_send = updatedRow.data()
    data_send['csrf_token'] = $('#csrf_token').val();
    post_request_api("user/tasks/status/update", JSON.stringify(data_send))
    .done((data) => {
        if (notify_auto_api(data)) {
           update_utasks_list();
           UserTaskTable.columns.adjust().draw();
        }
    });
}


/**** GTASKS ****/

/* Fetch a modal that allows to add an event */
function add_gtask() {
    url = '/global/tasks/add/modal' + case_param();
    $('#modal_add_gtask_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_gtask').on("click", function () {
            var data_sent = $('#form_new_gtask').serializeObject();
            data_sent['task_tags'] = $('#task_tags').val();
            data_sent['task_assignees_id'] = $('#task_assignees_id').val();
            data_sent['task_status_id'] = $('#task_status_id').val();
            data_sent['csrf_token'] = $('#csrf_token').val();

            post_request_api('/global/tasks/add', JSON.stringify(data_sent), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    update_gtasks_list();
                    $('#modal_add_gtask').modal('hide');
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
    data_sent['task_assignee_id'] = $('#task_assignee_id').val();
    data_sent['task_status_id'] = $('#task_status_id').val();
    data_sent['csrf_token'] = $('#csrf_token').val();

    post_request_api('/global/tasks/update/' + id, JSON.stringify(data_sent), true)
    .done((data) => {
        if(notify_auto_api(data)) {
            update_gtasks_list();
            $('#modal_add_gtask').modal('hide');
        }
    });
}

/* Delete an event from the timeline thank to its id */
function delete_gtask(id) {
    post_request_api("/global/tasks/delete/" + id)
    .done((data) => {
        if(notify_auto_api(data)) {
            update_gtasks_list();
            $('#modal_add_gtask').modal('hide');
        }
    });
}

/* Edit and event from the timeline thanks to its ID */
function edit_gtask(id) {
  url = '/global/tasks/update/'+ id + "/modal" + case_param();
  $('#modal_add_gtask_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        $('#modal_add_gtask').modal({show:true});
  });
}


/* Fetch and draw the tasks */
async function update_gtasks_list() {
    $('#gtasks_list').empty();

    return get_request_api("/global/tasks/list")
    .done((data) => {
        if(notify_auto_api(data, true)) {
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

            load_menu_mod_options('global_task', Table, delete_gtask);
            $('#tasks_last_updated').text("Last updated: " + new Date().toLocaleTimeString());
        }
    });
}


$(document).ready(function() {

        UserReviewsTable = $("#ureview_table").DataTable({
            dom: 'frtip',
            aaData: [],
            aoColumns: [
              {
                  "data": "name",
                  "render": function (data, type, row, meta) {
                    if (type === 'display') {
                        data = `<a  href="/case?cid=${row['case_id']}">${sanitizeHTML(data)}</a>`;
                    }
                    return data;
                    }
                },
                {
                    "data": "status_name",
                    "render": function (data, type, row, meta) {
                        if (type === 'display') {
                            data = `<span class="badge badge-light">${sanitizeHTML(data)}</span>`;
                        }
                        return data;
                    }
                }
            ],
            ordering: false,
            processing: true,
            retrieve: true,
            lengthChange: false,
            pageLength: 10,
            order: [[ 1, "asc" ]],
            select: true
        });

        UserCasesTable = $("#ucases_table").DataTable({
            dom: 'Blfrtip',
            aaData: [],
            aoColumns: [
              {
                "data": "name",
                "render": function (data, type, row, meta) {
                  if (type === 'display') {
                    data = `<a rel="noopener" target="_blank" href="/case?cid=${row['case_id']}">${sanitizeHTML(data)}</a>`;
                  }
                  return data;
                }
              },
              {
                 "data": "description",
                  "render": function (data, type, row, meta) {
                    if (type === 'display') {
                        data = sanitizeHTML(data);
                        datas = '<span data-toggle="popover" style="cursor: pointer;" title="Info" data-trigger="hover" href="#" data-content="' + data + '">' + data.slice(0, 70);

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
                "data": "client",
                "render": function(data, type, row, meta) {
                   if (type === 'display') {
                      //data = sanitizeHTML(data);
                      data = sanitizeHTML(row['client']['customer_name']);
                  }
                  return data;
                }
              },
              {
                "data": "open_date",
                "render": function (data, type, row, meta) {
                    if (type === 'display') {
                        data = sanitizeHTML(data);
                    }
                    return data;
                  }
              },
              {
                "data": "tags",
                "render": function (data, type, row, meta) {
                  if (type === 'display' && data != null) {
                    datas = '';
                    for (index in data) {
                        datas += '<span class="badge badge-primary">' + sanitizeHTML(data[index]['tag_title']) + '</span> ';
                    }
                    return datas;
                  }
                  return data;
                }
              }
        ],
        filter: true,
        info: true,
        ordering: true,
        processing: true,
        retrieve: true,
        lengthChange: false,
        pageLength: 10,
        order: [[ 2, "asc" ]],
        buttons: [
            { "extend": 'csvHtml5', "text":'Export',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
            { "extend": 'copyHtml5', "text":'Copy',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
        ],
        select: true
    });

    $("#ucases_table").css("font-size", 12);

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
                data = '<a target="_blank" rel="noopener" href="case/tasks?cid='+ row['case_id'] + '&shared=' + row['task_id'] + '">' + data +'</a>';
              }
              return data;
            }
          },
          { "data": "task_description",
           "render": function (data, type, row, meta) {
              if (type === 'display') {
                data = sanitizeHTML(data);
                datas = '<span data-toggle="popover" style="cursor: pointer;" title="Info" data-trigger="hover" href="#" data-content="' + data + '">' + data.slice(0, 70);

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
        order: [[ 2, "asc" ]],
        buttons: [
            { "extend": 'csvHtml5', "text":'Export',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
            { "extend": 'copyHtml5', "text":'Copy',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
        ],
        select: true
    });
    $("#utasks_table").css("font-size", 12);

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
                datas = '<span data-toggle="popover" style="cursor: pointer;" title="Info" data-trigger="hover" href="#" data-content="' + data + '">' + data.slice(0, 70);

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
        order: [[ 2, "asc" ]],
        buttons: [
            { "extend": 'csvHtml5', "text":'Export',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
            { "extend": 'copyHtml5', "text":'Copy',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
        ],
        select: true
    });
    $("#gtasks_table").css("font-size", 12);

    update_utasks_list();
    update_ucases_list();
    update_ureviews_list();
    setInterval(check_page_update,30000);
});