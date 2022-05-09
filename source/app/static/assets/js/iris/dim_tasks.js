$.each($.find("table"), function(index, element){
    addFilterFields($(element).attr("id"));
});


Table = $("#activities_table").DataTable({
    dom: 'Blfrtip',
    aaData: [],
    bSort: false,
    aoColumns: [

    { "data": "task_id",
    "render": function (data, type, row, meta) {
        if (type === 'display') {
            data = sanitizeHTML(data);
            data = "<a href='#' onclick=\"dim_task_status('"+ data +"');return false;\">"+ data +"</a>"
        }
        return data;
      } },
      {  "data": "state",
        "render": function (data, type, row, meta) {
            if (type === 'display') {
                if (data == 'success'){
                    data = "<i class='fas fa-check text-success' title='success'></i>";
                } else {
                    data = "<i class='fas fa-times text-danger' title='failure'></i>";
                }
            }
            return data;
       } },
      { "data": "date_done",
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
      { "data": "case",
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
      { "data": "module",
        "render": function (data, type, row, meta) {
        if (type === 'display') { data = sanitizeHTML(data);}
        return data;
      } },
      { "data": "user",
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
        url: '/dim/tasks/list/10000' + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
            jsdata = data;
            if (jsdata.status == "success") {
                content = jsdata.data;
                Table.clear();
                Table.rows.add(content);
                Table.columns.adjust().draw();
                $('#feed_last_updated').text("Last updated: " + new Date().toLocaleTimeString());
                hide_loader();
            } else {
                $('#modal_customer_message').text(jsdata.message);
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