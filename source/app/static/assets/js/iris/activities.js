Table = $("#activities_table").DataTable({
    dom: 'Blfrtip',
    aaData: [],
    bSort: false,
    aoColumns: [
      { "data": "activity_date" },
      { "data": "user_name" },
      { "data": "case_name" },
      { "data": "user_input" },
      { "data": "activity_desc" }
    ],
    filter: true,
    info: true,
    processing: true,
    retrieve: true,
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