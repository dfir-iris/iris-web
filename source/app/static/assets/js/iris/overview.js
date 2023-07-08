$.each($.find("table"), function(index, element){
    addFilterFields($(element).attr("id"));
});
var OverviewTable = $("#overview_table").DataTable({
    dom: '<"container-fluid"<"row"<"col"l><"col"f>>>rt<"container-fluid"<"row"<"col"i><"col"p>>>',
    aaData: [],
    aoColumns: [
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
            tableFiltering(this.api(), 'overview_table');
        }
    });

OverviewTable.searchBuilder.container().prependTo(OverviewTable.table().container());

function get_cases_overview(silent, show_full=false) {
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
            $('#overviewLoadClosedCase').prop('checked', show_full);
        }
    });
}

$(document).ready(function() {
    get_cases_overview(true);
});