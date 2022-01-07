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
                data = sanitizeHTML(data);
                if (row['ioc_misp'] != null) {
                    jse = JSON.parse(row['ioc_misp']);
                    data += `<i class="fas fa-exclamation-triangle ml-2 text-warning" style="cursor: pointer;" data-html="true"
                       data-toggle="popover" data-trigger="focus" title="Seen on MISP" data-content="Has been seen on  <a href='` + row['misp_link'] + `/events/view/` + jse.misp_id +`'>this event</a><br/><br/><b>Description: </b>`+ jse.misp_desc +`"></i>`;
                }
            }
            return data;
          }
       },
      { "data": "ioc_description",
        "render": function (data, type, row, meta) {
            if (type === 'display') {
                 data = sanitizeHTML(data);
                datas = '<span data-toggle="popover" style="cursor: pointer;" data-trigger="focus" title="Description" data-content="' + data + '">' + data.slice(0, 70);

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
      { "data": "type_name",
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }},
      { "data": "case_name",
         "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
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



$('#submit_search').click(function () {
    search();
});


function search() {
    var data_sent = $('form#form_search').serializeObject();
    data_sent['csrf_token'] = $('#csrf_token').val();

    $.ajax({
        url: '/search' + case_param(),
        type: "POST",
        data: JSON.stringify(data_sent),
        contentType: "application/json;charset=UTF-8",
        dataType: "json",
        beforeSend: function (data) {
            $('#submit_search').text("Searching...");
        },
        complete: function (data) {
            $('#submit_search').text("Search");
        },
        success: function (data) {
            jsdata = data;
            if (jsdata.status == "success") {
                  $('#notes_msearch_list').empty();
                  Table_1.clear();
                  $('#search_table_wrapper_1').hide();
                  $('#search_table_wrapper_2').hide();
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
                        li = `<li class="list-group-item">
                        <span class="name" style="cursor:pointer" title="Click to open note" onclick="note_detail(`+ data.data[e][0] +`);">`+ sanitizeHTML(data.data[e][3]) + ` - ` + sanitizeHTML(data.data[e][2]) + ` - ` + sanitizeHTML(data.data[e][1]) +`</span>
                        </li>`
                        $('#notes_msearch_list').append(li);
                    }
                    $('#search_table_wrapper_2').show();
                }
            }
        },
        error: function (error) {
            notify_error(error.responseJSON.message);
        }
    });
}
