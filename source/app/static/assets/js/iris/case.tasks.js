var current_users_list = [];
/* Fetch a modal that allows to add an event */
function add_task() {
    url = 'tasks/add/modal' + case_param();
    $('#modal_add_task_content').load(url, function (response, status, xhr) {
        hide_minimized_modal_box();
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_task').on("click", function () {

            clear_api_error();
            if(!$('form#form_new_task').valid()) {
                return false;
            }

            var data_sent = $('#form_new_task').serializeObject();
            data_sent['task_tags'] = $('#task_tags').val();
            data_sent['task_assignees_id'] = $('#task_assignees_id').val();
            data_sent['task_status_id'] = $('#task_status_id').val();
            ret = get_custom_attributes_fields();
            has_error = ret[0].length > 0;
            attributes = ret[1];

            if (has_error){return false;}

            data_sent['custom_attributes'] = attributes;

            post_request_api('tasks/add', JSON.stringify(data_sent), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    get_tasks();
                    $('#modal_add_task').modal('hide');
                }
            });

            return false;
        })
        $('#modal_add_task').modal({ show: true });
    });

}

function update_task(id) {

    clear_api_error();
    if(!$('form#form_new_task').valid()) {
        return false;
    }

    var data_sent = $('#form_new_task').serializeObject();
    data_sent['task_tags'] = $('#task_tags').val();

    data_sent['task_assignees_id'] = $('#task_assignees_id').val();
    data_sent['task_status_id'] = $('#task_status_id').val();
    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;

    $('#update_task_btn').text('Updating..');

    post_request_api('tasks/update/' + id, JSON.stringify(data_sent), true)
    .done((data) => {
        if(notify_auto_api(data)) {
            get_tasks();
            $('#modal_add_task').modal('hide');
        }
    })
    .always(() => {
        $('#update_task_btn').text('Update');
    });
}

/* Delete an event from the timeline thank to its id */ 
function delete_task(id) {

    get_request_api("tasks/delete/" + id)
    .done((data) => {
        if(notify_auto_api(data)) {
            get_tasks();
            $('#modal_add_task').modal('hide');
        }
    });
}

/* Edit and event from the timeline thanks to its ID */
function edit_task(id) {
  url = '/case/tasks/'+ id + '/modal' + case_param();
  $('#modal_add_task_content').load(url, function (response, status, xhr) {
        hide_minimized_modal_box();
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        load_menu_mod_options_modal(id, 'task', $("#task_modal_quick_actions"));
        $('#modal_add_task').modal({show:true});
  });
}

/* Fetch and draw the tasks */
function get_tasks() {
    $('#tasks_list').empty();
    show_loader();

    get_request_api("tasks/list")
    .done((data) => {
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
                        "options": options
                      }
                    ]
                  });

                Table.columns.adjust().draw();
                load_menu_mod_options('task', Table);
                $('[data-toggle="popover"]').popover();

                set_last_state(data.data.state);
                hide_loader();
            }

    });
}

function refresh_users(on_finish, cur_assignees_id_list) {

    get_request_api('/case/users/list')
    .done((data) => {

        if(notify_auto_api(data, true)) {
            current_users_list = data.data;

            if (on_finish !== undefined) {
                on_finish(current_users_list, cur_assignees_id_list);
            }

        }

    });

}

function do_list_users(list_users, cur_assignees_id_list) {

    $('#task_assignees_id').selectpicker({
        liveSearch: true,
        title: "Select assignee(s)"
    });

    for (user in list_users) {
        $('#task_assignees_id').append(new Option(`${list_users[user].user_login} (${list_users[user].user_name})`,
                                                    list_users[user].user_id));
    }

    if (cur_assignees_id_list !== undefined) {
        $('#task_assignees_id').selectpicker('val', cur_assignees_id_list);
    }

    $('#task_assignees_id').selectpicker('refresh');
}

function callBackEditTaskStatus(updatedCell, updatedRow, oldValue) {
  data_send = updatedRow.data();
  data_send['csrf_token'] = $('#csrf_token').val();
  tid = data_send['task_id'];

  post_request_api("tasks/status/update/" + tid, JSON.stringify(data_send))
  .done(function (data){
    if(notify_auto_api(data)) {
         get_tasks();
    }
  });
}

/* Page is ready, fetch the assets of the case */
$(document).ready(function(){

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
              if (type === 'display' && data != null) {

                if (isWhiteSpace(data)) {
                    data = '#' + row['task_id'];
                } else {
                    data = sanitizeHTML(data);
                }
                share_link = buildShareLink(row['task_id']);
                data = '<a href="'+ share_link + '" data-selector="true" title="Task ID #'+ row['task_id'] +'"  onclick="edit_task(\'' + row['task_id'] + '\');return false;">' + data +'</a>';
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
            "render": function(data, type, row) {
               if (type === 'display') {
                  data = sanitizeHTML(data);
                  data = '<span class="badge ml-2 badge-'+ row['status_bscolor'] +'">' + row['status_name'] + '</span>';
               }
               else if (type === 'filter' || type === 'sort'){
                  data = row['status_name']
               }
              return data;
            }
          },
          {
            "data": "task_assignees",
            "render": function (data, type, row, meta) {
                if (data != null) {
                    names = "";

                    if (data.length > 0) {
                        lst = [];
                        data.forEach(function (item, index) { lst.push(item['name']); });
                        if (type === 'display') {
                            names = list_to_badges(lst, 'primary', 10, 'users');
                        }
                        else {
                            lst.forEach(function (item, index) {
                                names += `${sanitizeHTML(item)}`;
                            });
                        }
                    }
                    else {
                        if (type === 'display') {
                            names = '<span class="badge badge-light ml-2">' + "Unassigned" + '</span>';
                        }
                        else {
                            names = "Unassigned";
                        }
                    }

                    return names;

                }
                return data;

            }
          },
          {
            "data": "task_open_date",
            "render": function (data, type, row, meta) { return sanitizeHTML(data);}
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
        pageLength: 50,
        order: [[ 2, "asc" ]],
        buttons: [
        ],
        orderCellsTop: true,
        initComplete: function () {
            tableFiltering(this.api(), 'tasks_table');
        },
        select: true
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

    get_tasks();
    setInterval(function() { check_update('tasks/state'); }, 3000);

    shared_id = getSharedLink();
    if (shared_id) {
        edit_task(shared_id);
    }
});
