/*************************
 *  Case creation section 
 *************************/

/* create the select picker for customer */
$('#case_customer').selectpicker({
    liveSearch: true,
    title: "Select customer *",
    style: "btn-outline-white",
    size: 8
});
$('#case_template_id').selectpicker({
    liveSearch: true,
    title: "Select case template",
    style: "btn-outline-white",
    size: 8
});
$('#case_template_id').prepend(new Option('', ''));
$('#classification_id').selectpicker({
    liveSearch: true,
    title: "Select classification",
    style: "btn-outline-white",
    size: 8
});
$('#classification_id').prepend(new Option('', ''));


 /*************************
 *  Case list section 
 *************************/
/* case table creation */
$.each($.find("table"), function(index, element){
    addFilterFields($(element).attr("id"));
});
$('#cases_table').dataTable({
    "ajax": {
        "url": "cases/list" + case_param(),
        "contentType": "application/json",
        "type": "GET",
        "data": function (d) {
            if (d.status == 'success') {
                return JSON.stringify(d.data);
            } else {
                return [];
            }
        }
    },
    "columns": [
        {
            "render": function (data, type, row) {
               let a_anchor = $('<a>');
                a_anchor.attr('href', 'javascript:void(0);');
                a_anchor.attr('onclick', 'case_detail(\'' + row['case_id'] + '\');');
                a_anchor.text(data);
                return a_anchor[0].outerHTML;
            },
            "data": "case_name"
        },
        {
            "data": "case_description",
            "render": function (data, type, row) {
                if (type === 'display' && data != null) {
                    return ret_obj_dt_description(data);
                }
                return data;
            },
        },
        {
            "data": "client_name",
            "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
        },
        {
            "data": "state_name",
            "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
        },
        {
            "data": "case_open_date",
            "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
            },
            "type": "date"
        },
        {
            "data": "case_close_date",
            "type": "date",
            "render": function (data, type, row, meta) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
              }
        },
        {
            "data": "case_soc_id",
            "render": function (data, type, row, meta) {
                if (type === 'display') {
                    let span_anchor = $('<span>');
                    span_anchor.text(data);
                    return span_anchor.html();
                }
                return data;
              }
        },
        {
            "data": "opened_by",
            "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
        }
    ],
    dom: '<"container-fluid"<"row"<"col"l><"col"f>>>rt<"container-fluid"<"row"<"col"i><"col"p>>>',
    filter: true,
    info: true,
    ordering: true,
    processing: true,
    retrieve: true,
    lengthChange: true,
    pageLength: 25,
    select: true,
    sort: true,
    orderCellsTop: true,
    responsive: {
        details: {
            display: $.fn.dataTable.Responsive.display.childRow,
            renderer: $.fn.dataTable.Responsive.renderer.tableAll()
        }
    },
    initComplete: function () {
            tableFiltering(this.api(), 'cases_table');
        }
    }
);


$(document).ready(function() {

    if ($('.nav-tabs').length > 0) { // if .nav-tabs exists
        var hashtag = window.location.hash;
        if (hashtag!='') {
            $('.nav-item > a').removeClass('active').removeClass('show');
            $('.nav-item > a[href="'+hashtag+'"]').addClass('active');
             $('.nav-item > a[href="'+hashtag+'"]').addClass('show');
            $('.tab-content > div').removeClass('active');
            $(hashtag).addClass('active'); $(hashtag).addClass('show');
        }
    }

});

