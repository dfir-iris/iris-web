$.each($.find("table"), function(index, element){
    addFilterFields($(element).attr("id"));
});


Table = $("#activities_table").DataTable({
    dom: 'Blfrtip',
    aaData: [],
    bSort: false,
    aoColumns: [
      { "data": "activity_date",
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
      { "data": "user_name",
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
      { "data": "case_name",
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
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
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } }
    ],
    filter: true,
    info: true,
    processing: true,
    retrieve: true,
    initComplete: function () {
        tableFiltering(this.api());
    },
    buttons: [
    { "extend": 'csvHtml5', "text":'Export',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
    { "extend": 'copyHtml5', "text":'Copy',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
    ]
});
$("#activities_table").css("font-size", 12);


function get_activities () {
    $.ajax({
        url: '/activities/list' + case_param(),
        type: "GET",
        dataType: "JSON",
        success: function (data) {
            jsdata = data;
            if (jsdata.status == "success") {
                  Table.clear();
                  Table.rows.add(data.data);
                  Table.columns.adjust().draw();
                  Table.buttons().container().appendTo($('#activities_table_info'));

                hide_loader();
                notify_success("Activities refreshed");
            } 
        },
        error: function (error) {
            notify_error(error);
        }
    });

}

$(document).ready(function(){
    get_activities();
});