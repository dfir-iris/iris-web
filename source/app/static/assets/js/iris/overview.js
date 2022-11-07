function get_cases_overview() {
    get_request_api('overview/filter')
    .done((data) => {
        if(notify_auto_api(data, true)) {
            overview_list = data.data;
            OverviewTable.clear();
            OverviewTable.rows.add(overview_list);
            OverviewTable.columns.adjust().draw();
        }
    });
}

$(document).ready(function() {

    $.each($.find("table"), function(index, element){
        addFilterFields($(element).attr("id"));
    });

    OverviewTable = $("#overview_table").DataTable({
    dom: '<"container-fluid"<"row"<"col"l><"col"f>>>rt<"container-fluid"<"row"<"col"i><"col"p>>>',
    aaData: [],
    aoColumns: [
      {
        "data": "case_title",
        "render": function (data, type, row, meta) {
          if (type === 'display') {
            if (isWhiteSpace(data)) {
                data = '#' + row['case_id'];
            } else {
                data = sanitizeHTML(data);
            }
            data = '<a href="case/tasks?cid='+ row['case_id'] + '">' + data +'</a>';
          }
          return data;
        }
      },
      { "data": "case_description",
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
        "data": "case_open_since",
        "render": function(data, type, row, meta) {
           if (type === 'display') {
              data = sanitizeHTML(data);
          }
          return data;
        }
      },
      {
        "data": "case_open_date",
        "render": function (data, type, row, meta) {
            if (type === 'display' && data != null) {
              data = sanitizeHTML(data);
            }
            return data;
          }
      },
      {
        "data": "opened_by",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
              data = get_avatar_initials(sanitizeHTML(data), true);
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
    pageLength: 25,
    order: [[ 2, "asc" ]],
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

    get_cases_overview();
});