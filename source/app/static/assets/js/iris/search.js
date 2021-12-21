$('#search_value').keypress(function(event){
    var keycode = (event.keyCode ? event.keyCode : event.which);
    if(keycode == '13'){
        jQuery(this).blur();
        jQuery('#submit_search').focus().click();
        event.stopPropagation();
        return false;
    }
});

Table = $("#file_search_table").DataTable({
    dom: 'Bfrtip',
    aaData: [],
    aoColumns: [
      {
        "data": "content_hash",
        "render": function (data, type, row, meta) {
          if (type === 'display') {
            data = '<a  data-toggle="tooltip" title="' + data + '"href="details/hash=' + data + '">Hash detail</a>';
          }
          return data;
        }
      },
      { "data": "filename" },
      { "data": "path" },
      { "data": "vt_score" },
      { "data": "case_name" },
      { "data": "seen_count" },
      { "data": "flag" },
      { "data": "comment" },
      {
        "data": "vt_url",
        "render": function (data, type, row, meta) {
          if (type === 'display') {
            data = '<a href="' + data + '">Link</a>';
          }
          return data;
        }
      }
    ],
    createdRow: function (row, data, dataIndex) {
      if (data[6] > 2) {
        $(row).addClass('redClass');
      }
    },
    rowCallback: function (nRow, data) {
      if (data.flag == 1) {
        $(nRow).removeClass('table-danger').removeClass('table-warning').removeClass('table-success');
        $(nRow).addClass('table-danger');
      } else if (data.flag == 2) {
        $(nRow).removeClass('table-danger').removeClass('table-warning').removeClass('table-success');
        $(nRow).addClass('table-warning');
      }
      else if (data.flag == 3) {
        $(nRow).removeClass('table-danger').removeClass('table-warning').removeClass('table-success');
        $(nRow).addClass('table-success');
      }
      else {
        $(nRow).removeClass('table-danger').removeClass('table-warning').removeClass('table-success');
      }
    },
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
$("#file_search_table").css("font-size", 12);


Table_1 = $("#file_search_table_1").DataTable({
    dom: 'Bfrtip',
    aaData: [],
    aoColumns: [
      { "data": "ioc_name",
       "render": function (data, type, row, meta) {
            if (type === 'display') {
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
      { "data": "ioc_type" },
      { "data": "case_name" },
      { "data": "customer_name" },
      { "data": "tlp_name",
        "render": function(data, type, row, meta) {
            if (type === 'display') {
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
    $.ajax({
        url: '/search' + case_param(),
        type: "POST",
        data: $('form#form_search').serialize(),
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
                  //Table.destroy();
                  //Table_1.destroy();
                  Table.clear();
                  Table_1.clear();
                  $('#search_table_wrapper_1').hide();
                  $('#search_table_wrapper_2').hide();
                val = $("input[type='radio']:checked").val();
                if (val == "hashes" || val == "files") {
                      Table.MakeCellsEditable("destroy");

                      Table.rows.add(JSON.parse(data.data));
                      Table.columns.adjust().draw();
                      Table.MakeCellsEditable({
                        "onUpdate": '',
                        "inputCss": 'form-control',
                        "columns": [6, 7],
                        "allowNulls": {
                          "columns": [6, 7],
                          "errorClass": 'error'
                        },
                        "confirmationButton": {
                          "confirmCss": 'my-confirm-class',
                          "cancelCss": 'my-cancel-class'
                        },
                        "inputTypes": [
                          {
                            "column": 6,
                            "type": "text",
                            "options": null
                          },
                          {
                            "column": 7,
                            "type": "list",
                            "options": [
                              { "value": "1", "display": "Malicious" },
                              { "value": "2", "display": "Suspicious" },
                              { "value": "3", "display": "Healthy" },
                              { "value": "", "display": "Not flagged" }
                            ]
                          }
                        ]
                      });
                      $('#search_table_wrapper').show();
                      Table.buttons().container().appendTo($('#file_search_table_info'));

                }
                else if (val == "ioc") {
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
                        <span class="name" style="cursor:pointer" title="Click to open note" onclick="note_detail(`+ data.data[e][0] +`);">`+ data.data[e][3] + ` - ` + data.data[e][2] + ` - ` + data.data[e][1] +`</span>
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
