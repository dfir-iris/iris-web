$.each($.find("table"), function(index, element){
    addFilterFields($(element).attr("id"));
});


Table = $("#activities_table").DataTable({
    dom: 'Blfrtip',
    aaData: [],
    bSort: false,
    aoColumns: [
      { "data": "activity_date",
        "render":  $.fn.dataTable.render.text()
      },
        {
            "data": "user_name",
            "render": $.fn.dataTable.render.text()
        },
      { "data": "case_name",
        "render": $.fn.dataTable.render.text()
      },
      { "data": "user_input",
        "render": function (data, type, row, meta) {
            if (type === 'display') {
                if (data == true){
                    data = "<i class='fas fa-check text-success text-center'></i>";
                } else {
                    data = "<i class='fas fa-times text-muted'></i>";
                }
            }
            return data;
          } },
      { "data": "is_from_api",
        "render": function (data, type, row, meta) {
        if (type === 'display') {
            if (data == true){
                data = "<i class='fas fa-check text-success'></i>";
            } else {
                data = "<i class='fas fa-times text-muted'></i>";
            }

            }
        return data;
      } },
      { "data": "activity_desc",
        "render": $.fn.dataTable.render.text()
      }
    ],
    filter: true,
    info: true,
    processing: true,
    retrieve: true,
    initComplete: function () {
        tableFiltering(this.api(), 'activities_table');
    },
    buttons: [
    { "extend": 'csvHtml5', "text":'Export',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
    { "extend": 'copyHtml5', "text":'Copy',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
    ]
});
$("#activities_table").css("font-size", 12);

function refresh_activities() {
    get_activities ();
    notify_success('Refreshed');
}

function get_activities () {
    show_loader();
    if ($('#non_case_related_act').is(':checked')) {
        url = '/activities/list-all';
    } else {
        url = '/activities/list';
    }

    get_request_api(url)
    .done((data) => {
        if(notify_auto_api(data, true)) {
            jsdata = data;
            if (jsdata.status == "success") {
                  Table.clear();
                  Table.rows.add(data.data);
                  Table.columns.adjust().draw();
                  Table.buttons().container().appendTo($('#activities_table_info'));
                hide_loader();
            }
        }
    }).fail((data) => {
        hide_loader();
        Table.clear();
        Table.columns.adjust().draw();
    });
}

$(document).ready(function(){
    get_activities();
    $('#non_case_related_act').on('change', function() {
        get_activities();
    });
});