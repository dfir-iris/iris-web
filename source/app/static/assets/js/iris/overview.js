$.each($.find("table"), function(index, element){
    addFilterFields($(element).attr("id"));
});
var OverviewTable = $("#overview_table").DataTable({
    dom: '<"container-fluid"<"row"<"col"l><"col"f>>>rt<"container-fluid"<"row"<"col"i><"col"p>>>',
    aaData: [],
    aoColumns: [
      {
          data: "case_id",
            render: function (data, type, row, meta) {
                if (type === 'display') {
                    data = `<button class="btn bg-transparent btn-quick-view" data-index="${meta.row}" ><i class="fa-solid fa-binoculars"></i></button>`;
                } else if (type === 'sort' || type === 'filter') {
                    data = parseInt(row['case_id']);
                }
                return data;
            }
        },
      {
        "data": "name",
        "render": function (data, type, row, meta) {
          if (type === 'display') {
            if (isWhiteSpace(data)) {
                data = '#' + row['case_id'];
            } else {
                data = sanitizeHTML(data);
            }
            data = '<a rel="noopener" title="Open case in new tab" target="_blank" href="case?cid='+ row['case_id'] + '">' + data +'</a>';
          } else if (type === 'sort' || type === 'filter') {
            data = parseInt(row['case_id']);
          }
          return data;
        }
      },
      { "data": "client",
       "render": function (data, type, row, meta) {
          if (type === 'display') {
            data = sanitizeHTML(data.customer_name);
          } else if (type === 'sort' || type === 'filter') {
            data = sanitizeHTML(data.customer_name);
          }
          return data;
        }
      },
      {
        "data": "classification",
        "render": function (data, type, row, meta) {
            if (type === 'display' && data != null) {
                data = sanitizeHTML(data.name);
            } else if (data != null && (type === 'sort' || type === 'filter')) {
                data = data.name;
            }
            return data;
        }
      },
      {
        "data": "state",
        "render": function (data, type, row, meta) {
            if (type === 'display' && data != null) {
                data = sanitizeHTML(data.state_name);
            } else if (data != null && (type === 'sort' || type === 'filter')) {
                data = sanitizeHTML(data.state_name);
            }
            return data;
        }
      },
     {
        "data": "tags",
        "render": function (data, type, row, meta) {
            if (type === 'display' && data != null) {
                let output = '';
                for (let index in data) {
                    let tag = sanitizeHTML(data[index].tag_title);
                    output += `<span class="badge badge-pill badge-light">${tag}</span> `;
                }
                return output;
            } else if (type === 'sort' || type === 'filter') {
                let output = [];
                for (let index in data) {
                    let tag = sanitizeHTML(data[index].tag_title);
                    output.push(tag);
                }
                return output;
            }
            return data;
        }

     },
      {
        "data": "case_open_since_days",
        "render": function(data, type, row, meta) {
           if (type === 'display') {
              title = "You\'re not forgetting me, are you?";
              if (data <= 1) {
                data = `<i title="Sounds good" class="text-success fw-bold fa-solid fa-stopwatch mr-1"></i>${data} day`;
              }
              else if (data <= 7) {
                data = `<i title="Sounds good" class="text-success fw-bold fa-solid fa-stopwatch mr-1"></i>${data} days`;
              } else if (7 < data && data < 14) {
                data = `<i title="${title}" class="text-warning fw-bold fa-solid fa-stopwatch mr-1"></i>${data} days</div>`;
              } else {
                data = `<i title="${title}" class="text-danger fw-bold fa-solid fa-stopwatch mr-1"></i>${data} days</div>`;
              }
          } else if (type === 'sort' || type === 'filter') {
              data = parseInt(data);
          }
          return data;
        }
      },
      {
        "data": "open_date",
        "render": function (data, type, row, meta) {
            if (type === 'display' && data != null) {
              data = sanitizeHTML(data);
            }
            return data;
          }
      },
      {
        "data": "tasks_status",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
              now = (data.closed_tasks / (data.closed_tasks + data.open_tasks))*100;
              if (data.closed_tasks + data.open_tasks > 1) {
                 tasks_text = `tasks`;
              } else {
                tasks_text = `task`;
              }
              data = `<div class="progress progress-sm">
                    <div class="progress-bar bg-success" style="width:${now}%" role="progressbar" aria-valuenow="${now}" aria-valuemin="0" aria-valuemax="100"></div>
               </div><small class="float-right">${data.closed_tasks} / ${data.closed_tasks + data.open_tasks} ${tasks_text} done</small>`;
		  } else if (data != null && (type === 'sort' || type === 'filter')) {
              data = data.closed_tasks / (data.closed_tasks + data.open_tasks);
          }
          return data;
        }
      },
      {
        "data": "owner",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
              sdata = sanitizeHTML(data.user_name);
              data = `<div class="row">${get_avatar_initials(sdata, false, null, true)} <span class="mt-2 ml-1">${sdata}</span></div>`;
          } else if (type === 'filter') {
                data = data.user_name;
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
    lengthChange: true,
    pageLength: 25,
    searchBuilder: {
    },
    language: {
      searchBuilder: {
        add: "Add filter",
        title: {
            _: 'Filters (%d)',
            0: '',
        }
      }
    },
    order: [[ 1, "asc" ]],
    buttons: [
        { "extend": 'csvHtml5', "text":'Export',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
        { "extend": 'copyHtml5', "text":'Copy',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
    ],
    responsive: {
        details: {
            display: $.fn.dataTable.Responsive.display.childRow,
            renderer: $.fn.dataTable.Responsive.renderer.tableAll()
        }
    },
    select: true,
    initComplete: function () {
            tableFiltering(this.api(), 'overview_table', [0]);
        }
    });

OverviewTable.searchBuilder.container().appendTo($('#table_buttons'));

function get_cases_overview(silent, show_full=false) {
    show_full = show_full || $('#overviewLoadClosedCase').prop('checked');

     $('#overviewTableTitle').text(show_full ? 'All cases' : 'Open cases');

    get_raw_request_api('/overview/filter?cid=' + get_caseid() + (show_full ? '&show_closed=true' : ''))
    .done((data) => {
        if(notify_auto_api(data, silent)) {
            overview_list = data.data;
            OverviewTable.clear();
            OverviewTable.rows.add(overview_list);
            OverviewTable.columns.adjust().draw();
            $(".truncate").on("click", function() {
                var index = $(this).index() + 1;
                $('table tr td:nth-child(' + index  + ')').toggleClass("truncate");
            });

            $('.btn-quick-view').on('click', function() {
                show_case_view($(this).data('index'));
            });
        }
    });
}

function show_case_view(row_index) {
    let case_data = OverviewTable.row(row_index).data();
    $('#caseViewModal').find('.modal-title').text(case_data.name);
    $('#caseViewModal').find('.modal-subtitle').text(case_data.case_uuid);

    let body = $('#caseViewModal').find('.modal-body .container');
    body.empty();

    // Owner Card
    let owner_card = $('<div/>').addClass('card mb-3');
    let owner_body = $('<div/>').addClass('card-body');
    owner_body.append($('<h2/>').addClass('card-title mb-2').text('Metadata'));

    let owner_row = $('<div/>').addClass('row');
    let owner_col1 = $('<div/>').addClass('col-md-6');
    let owner_col2 = $('<div/>').addClass('col-md-6');

    let modifications = case_data.modification_history;
    let timestamps = Object.keys(modifications).map(parseFloat);
    let lastUpdatedTimestamp = Math.max(...timestamps);

    let currentTime = Date.now() / 1000; // convert to seconds
    let timeSinceLastUpdate = currentTime - lastUpdatedTimestamp;
    let timeSinceLastUpdateInSeconds = currentTime - lastUpdatedTimestamp;

    let timeSinceLastUpdateInMinutes = timeSinceLastUpdate / 60;
    let timeSinceLastUpdateInHours = timeSinceLastUpdateInMinutes / 60;
    let timeSinceLastUpdateInDays = timeSinceLastUpdateInHours / 24;

    let timeSinceLastUpdateStr = '';
    if (timeSinceLastUpdateInSeconds < 60) {
        timeSinceLastUpdateStr = `${Math.round(timeSinceLastUpdateInSeconds)} second(s) ago`;
    } else if (timeSinceLastUpdateInMinutes < 60) {
        timeSinceLastUpdateStr = `${Math.round(timeSinceLastUpdateInMinutes)} minute(s) ago`;
    }
    else if (timeSinceLastUpdateInHours < 24) {
        timeSinceLastUpdateStr = `${Math.round(timeSinceLastUpdateInHours)} hour(s) ago`;
    } else {
        timeSinceLastUpdateStr = `${Math.round(timeSinceLastUpdateInDays)} day(s) ago`;
    }

    let tagsStr = '';
    for (let index in case_data.tags) {
        let tag = sanitizeHTML(case_data.tags[index].tag_title);
        tagsStr += `<span class="badge badge-pill badge-light">${tag}</span> `;
    }

    let owner_dl1 = $('<dl/>');
    owner_dl1.append($('<dt/>').text('Owner'));
    owner_dl1.append($('<dd/>').text(case_data.owner.user_name));
    owner_dl1.append($('<dt/>').text('Opening User'));
    owner_dl1.append($('<dd/>').text(case_data.user.user_name));
    owner_dl1.append($('<dt/>').text('Open Date'));
    owner_dl1.append($('<dd/>').text(case_data.open_date));

    if (case_data.close_date != null) {
        owner_dl1.append($('<dt/>').text('Close Date'));
        owner_dl1.append($('<dd/>').text(case_data.close_date))
    }
    owner_dl1.append($('<dt/>').text('Tags'));
    owner_dl1.append($('<dd/>').html(tagsStr));
    owner_dl1.append($('<dt/>').text('State'));
    owner_dl1.append($('<dd/>').text(case_data.state.state_description));
    owner_dl1.append($('<dt/>').text('Last update'));
    owner_dl1.append($('<dd/>').text(timeSinceLastUpdateStr));


    owner_col1.append(owner_dl1);



    let owner_dl2 = $('<dl/>');
    owner_dl2.append($('<dt/>').text('Customer Name'));
    owner_dl2.append($('<dd/>').text(case_data.client.customer_name));
    owner_dl2.append($('<dt/>').text('Classification'));
    owner_dl2.append($('<dd/>').text(case_data.classification.name));
    owner_dl2.append($('<dt/>').text('SOC ID'));
    owner_dl2.append($('<dd/>').text(case_data.soc_id));
    owner_dl2.append($('<dt/>').text('Related alerts'));
    owner_dl2.append($('<dd/>').html(`<a target="_blank" rel="noopener" href='/alerts?case_id=${case_data.case_id}'>${case_data.alerts.length} related alert(s) <i class="fa-solid fa-up-right-from-square ml-2"></i></a>`));
    owner_dl2.append($('<dt/>').text('Tasks'));
    if (case_data.tasks_status != null) {
        owner_dl2.append($('<dd/>').html(`<a target="_blank" rel="noopener" href='/case/tasks?cid=${case_data.case_id}'>${case_data.tasks_status.closed_tasks}/${case_data.tasks_status.open_tasks + case_data.tasks_status.closed_tasks} task(s) <i class="fa-solid fa-up-right-from-square ml-2"></i></a>`));
    } else {
        owner_dl2.append($('<dd/>').text('No tasks'));
    }

    owner_col2.append(owner_dl2);

    owner_row.append(owner_col1);
    owner_row.append(owner_col2);
    owner_body.append(owner_row);
    owner_body.append('<a type="button" class="btn btn-sm btn-dark float-right" target="_blank" rel="noopener" href=\'/case?cid=${case_data.case_id}\'><i class="fa-solid fa-up-right-from-square mr-2"></i> View case</a>');

    owner_card.append(owner_body);
    body.append(owner_card);

    // Description Card
    let desc_card = $('<div/>').addClass('card mb-3');
    let desc_body = $('<div/>').addClass('card-body');
    desc_body.append($('<h2/>').addClass('card-title mb-3').text('Summary'));
    let converter = get_showdown_convert();
    let html = converter.makeHtml(case_data.description);
    desc_body.append($('<div/>').addClass('card-text').html(html));

    desc_card.append(desc_body);
    body.append(desc_card);


    $('#caseViewModal').modal('show');
}

$(document).ready(function() {
    get_cases_overview(true);


    $('#overviewLoadClosedCase').change(function() {
        get_cases_overview(true, this.checked);
    });

});