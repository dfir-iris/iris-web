$('#search_value').keypress(function(event){
    var keycode = (event.keyCode ? event.keyCode : event.which);
    if(keycode == '13'){
        jQuery(this).blur();
        jQuery('#submit_search').focus().click();
        event.stopPropagation();
        return false;
    }
});


Table_1 = $("#file_search_table_1").DataTable({
    dom: 'Bfrtip',
    aaData: [],
    aoColumns: [
      { "data": "ioc_name",
       "render": function (data, type, row, meta) {
            if (type === 'display') {
                let span_anchor = $('<span>');
                span_anchor.text(data);
                return span_anchor.html();
            }
            return data;
          }
       },
      { "data": "ioc_description",
        "render": function (data, type, row, meta) {
            if (type === 'display') {
                return ret_obj_dt_description(data);
            }
            return data;
          }
      },
      { "data": "type_name",
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }},
      { "data": "case_name",
         "render": function (data, type, row, meta) {
            if (type === 'display') {
                let a_anchor = $('<a>');
                a_anchor.attr('href', 'case?cid=' + row["case_id"]);
                a_anchor.attr('target', '_blank');
                a_anchor.text(data);
                return a_anchor[0].outerHTML;
            }
            return data;
          }},
      { "data": "customer_name",
         "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          } },
      { "data": "tlp_name",
        "render": function(data, type, row, meta) {
            if (type === 'display') {
                data = sanitizeHTML(data);
                data = '<span class="badge badge-'+ row['tlp_bscolor'] +' ml-2">tlp:' + data + '</span>';
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
    buttons: [
    { "extend": 'csvHtml5', "text":'Export',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
    { "extend": 'copyHtml5', "text":'Copy',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
    ]
});
$("#file_search_table_1").css("font-size", 12);

Table_comments = $("#comments_search_table").DataTable({
    dom: 'Bfrtip',
    aaData: [],
    aoColumns: [
      { "data": "comment_id",
       "render": function (data, type, row, meta) {
            if (type === 'display') {
                data = sanitizeHTML(data);
                if (row['ioc_misp'] != null) {
                    jse = JSON.parse(row['ioc_misp']);
                    data += `<i class="fas fa-exclamation-triangle ml-2 text-warning" style="cursor: pointer;" data-html="true"
                       data-toggle="popover" data-trigger="hover" title="Seen on MISP" data-content="Has been seen on  <a href='` + row['misp_link'] + `/events/view/` + jse.misp_id +`'>this event</a><br/><br/><b>Description: </b>`+ jse.misp_desc +`"></i>`;
                }
            }
            return data;
          }
       },
      { "data": "comment_text",
        "render": function (data, type, row, meta) {
            if (type === 'display') {
               return ret_obj_dt_description(data);
            }
            return data;
          }
      },
      { "data": "case_name",
         "render": function (data, type, row, meta) {
            let a_anchor = $('<a>');
            a_anchor.attr('href', 'case?cid=' + row["case_id"]);
            a_anchor.attr('target', '_blank');
            a_anchor.text(data);
            return a_anchor[0].outerHTML;
          }},
      { "data": "customer_name",
         "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
      }
    ],
    filter: true,
    info: true,
    ordering: true,
    processing: true,
    retrieve: true,
    buttons: [
    { "extend": 'csvHtml5', "text":'Export',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
    { "extend": 'copyHtml5', "text":'Copy',"className": 'btn btn-primary btn-border btn-round btn-sm float-left mr-4 mt-2' },
    ]
});
$("#comments_search_table").css("font-size", 12);

$('#submit_search').click(function () {
    search();
});


function search() {
    var data_sent = $('form#form_search').serializeObject();
    data_sent['csrf_token'] = $('#csrf_token').val();
    post_request_api('/search', JSON.stringify(data_sent), true, function (data) {
            $('#submit_search').text("Searching...");
    })
    .done((data) => {
        if(notify_auto_api(data, true)) {
              $('#notes_msearch_list').empty();
              Table_1.clear();
              Table_comments.clear();
              $('#search_table_wrapper_1').hide();
              $('#search_table_wrapper_2').hide();
              $('#search_table_wrapper_3').hide();
            val = $("input[type='radio']:checked").val();
            if (val == "ioc") {
                Table_1.rows.add(data.data);
                Table_1.columns.adjust().draw();
                $('#search_table_wrapper_1').show();

                $('#search_table_wrapper_1').on('click', function(e){
                    if($('.popover').length>1)
                        $('.popover').popover('hide');
                        $(e.target).popover('toggle');
                });
            }
            else if (val == "notes") {
                for (e in data.data) {
                    let li_anchor = $('<i>');
                    li_anchor.addClass('list-group-item');
                    let span_anchor = $('<span>');
                    span_anchor.addClass('name');
                    span_anchor.attr('style', 'cursor:pointer');
                    span_anchor.attr('title', 'Click to open note');
                    span_anchor.attr('onclick', 'note_in_details(' + data.data[e]['note_id'] + ', ' + data.data[e]['case_id'] + ');');
                    span_anchor.text(data.data[e]['note_title'] + ' - ' + data.data[e]['case_name'] + ' - ' + data.data[e]['client_name']);
                    li_anchor.append(span_anchor);
                    $('#notes_msearch_list').append(li_anchor);

                }
                $('#search_table_wrapper_2').show();
            } else if (val == "comments") {
                Table_comments.rows.add(data.data);
                Table_comments.columns.adjust().draw();
                $('#search_table_wrapper_3').show();

                $('#search_table_wrapper_3').on('click', function(e){
                    if($('.popover').length>1)
                        $('.popover').popover('hide');
                        $(e.target).popover('toggle');
                });
            }
        }
    })
    .always(() => {
        $('#submit_search').text("Search");
    });
}

function note_in_details(note_id, case_id) {
    window.open("/case/notes?cid=" + case_id + "&shared=" + note_id);

}

$(document).ready(function(){
    $('#search_value').focus();
});
