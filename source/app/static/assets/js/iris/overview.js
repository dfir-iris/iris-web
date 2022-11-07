$(document).ready(function() {

    OverviewTable = $("#overview_table").DataTable({
    dom: 'Blfrtip',
    aaData: [],
    aoColumns: [
      {
        "data": "case_title",
        "render": function (data, type, row, meta) {
          if (type === 'display') {
            if (isWhiteSpace(data)) {
                data = '#' + row['task_id'];
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
              data = data.replace(/GMT/g, "");
            }
            return data;
          }
      },
      {
        "data": "opened_by",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
              data = sanitizeHTML(data);
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

    get_cases_overview();
});