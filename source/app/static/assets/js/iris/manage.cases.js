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


/* Submit event handler for new case */
function submit_new_case() {

    if(!$('form#form_new_case').valid()) {
        return false;
    }

    var data_sent = $('form#form_new_case').serializeObject();
    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;

    send_add_case(data_sent);

    return false;
};


function send_add_case(data_sent) {

    post_request_api('/manage/cases/add', JSON.stringify(data_sent), true, function () {
        $('#submit_new_case_btn').text('Checking data..')
            .attr("disabled", true)
            .removeClass('bt-outline-success')
            .addClass('btn-success', 'text-dark');
    })
    .done((data) => {
        if (notify_auto_api(data, true)) {
            case_id = data.data.case_id;
            swal("That's done !",
                "Case has been successfully created",
                "success",
                {
                    buttons: {
                        again: {
                            text: "Create a case again",
                            value: "again",
                            dangerMode: true,
                            color: '#d33'
                        },
                        dash: {
                            text: "Go to dashboard",
                            value: "dash",
                            color: '#d33'
                        },
                        go_case: {
                            text: "Switch to newly created case",
                            value: "go_case"
                        }
                    }
                }
            ).then((value) => {
                switch (value) {

                    case "dash":
                        window.location.replace("/dashboard" + case_param());
                        break;

                    case "again":
                        window.location.replace("/manage/cases" + case_param());
                        break;

                    case 'go_case':
                        window.location.replace("/case?cid=" + case_id);

                    default:
                        window.location.replace("/case?cid=" + case_id);
                }
            });
        }
    })
    .always(() => {
        $('#submit_new_case_btn')
        .attr("disabled", false)
        .addClass('bt-outline-success')
        .removeClass('btn-success', 'text-dark');
    })
    .fail(() => {
        $('#submit_new_case_btn').text('Save');
    })

}

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
                data = sanitizeHTML(data);
                return '<a href="#" onclick="case_detail(\'' + row['case_id'] + '\');">' + data + '</a>';
            },
            "data": "case_name"
        },
        {
            "data": "case_description",
            "render": function (data, type, row) {
                if (type === 'display' && data != null) {
                    if (row["case_description"].length > 50){
                        return sanitizeHTML(row["case_description"].slice(0,50)) + " ... " ;
                    }
                    else {
                        return sanitizeHTML(row["case_description"]);
                    }
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
                if (type === 'display') { data = sanitizeHTML(data);}
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

