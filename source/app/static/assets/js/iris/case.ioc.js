/* reload the ioc table */
function reload_iocs() {
    get_case_ioc();
}

/* add filtering fields for each table of the page (must be done before datatable initialization) */
$.each($.find("table"), function(index, element){
    addFilterFields($(element).attr("id"));
});

Table = $("#ioc_table").DataTable({
    dom: 'Blfrtip',
    fixedHeader: true,
    aaData: [],
    aoColumns: [
      {
        "data": "ioc_value",
        "render": function (data, type, row, meta) {
          if (type === 'display') {
            datak= sanitizeHTML(data);
            if (data.length > 60) {
                datak = data.slice(0, 60) + " (..)";
            }

            if (isWhiteSpace(data)) {
                datak = '#' + row['ioc_id'];
            }

            share_link = buildShareLink(row['ioc_id']);
            data = '<a href="' + share_link + '" data-selector="true" title="IOC ID #'+ row['ioc_id'] +'"  onclick="edit_ioc(\'' + row['ioc_id'] + '\');return false;">' + datak +'</a>';
            if (row['ioc_misp'] != null) {
                jse = JSON.parse(row['ioc_misp']);
                data += `<i class="fas fa-exclamation-triangle ml-2 text-warning" style="cursor: pointer;" data-html="true"
                   data-toggle="popover" data-trigger="hover" title="Seen on MISP" data-content="Has been seen on  <a href='` + row['misp_link'] + `/events/view/` + jse.misp_id +`'>this event</a><br/><br/><b>Description: </b>`+ jse.misp_desc +`"></i>`;
            }
          }
          return data;
        }
      },
      { "data": "ioc_type",
       "render": function (data, type, row, meta) {
          if (type === 'display') {
            data = sanitizeHTML(data);
          }
          return data;
          }
      },
      { "data": "ioc_description",
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
      { "data": "ioc_tags",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
              tags = "";
              de = data.split(',');
              for (tag in de) {
                tags += '<span class="badge badge-light ml-2">' + sanitizeHTML(de[tag]) + '</span>';
              }
              return tags;
          }
          return data;
        }
      },
      { "data": "link",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
              links = "";
              for (link in data) {
                links += '<span data-toggle="popover" style="cursor: pointer;" data-trigger="hover" class="text-primary mr-3" href="#" title="Case info" data-content="' + sanitizeHTML(data[link]['case_name']) +
                 ' (' + sanitizeHTML(data[link]['client_name']) + ')' + '">#' + data[link]['case_id'] + '</span>'
              }
              return links;
          }
          return data;
        }
      },
      {
        "data": "tlp_name",
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
    responsive: {
        details: {
            display: $.fn.dataTable.Responsive.display.modal( {
                header: function ( row ) {
                    var data = row.data();
                    return 'Details for '+data[0]+' '+data[1];
                }
            } ),
            renderer: $.fn.dataTable.Responsive.renderer.tableAll()
        }
    },
    buttons: [],
    orderCellsTop: true,
    initComplete: function () {
        tableFiltering(this.api());
    },
    select: true
});
$("#ioc_table").css("font-size", 12);

var buttons = new $.fn.dataTable.Buttons(Table, {
     buttons: [
        { "extend": 'csvHtml5', "text":'<i class="fas fa-cloud-download-alt"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Download as CSV' },
        { "extend": 'copyHtml5', "text":'<i class="fas fa-copy"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Copy' },
    ]
}).container().appendTo($('#tables_button'));

Table.on( 'responsive-resize', function ( e, datatable, columns ) {
        hide_table_search_input( columns );
});

/* Fetch a modal that is compatible with the requested ioc type */ 
function add_ioc() {
    url = 'ioc/add/modal' + case_param();

    $('#modal_add_ioc_content').load(url, function () {   
        $('#submit_new_ioc').on("click", function () {
            if(!$('form#form_new_ioc').valid()) {
                return false;
            }

            var data = $('#form_new_ioc').serializeObject();
            data['ioc_tags'] = $('#ioc_tags').val();
            ret = get_custom_attributes_fields();
            has_error = ret[0].length > 0;
            attributes = ret[1];

            if (has_error){return false;}

            data['custom_attributes'] = attributes;

            id = $('#ioc_id').val();
            $.ajax({
                url: 'ioc/add' + case_param(),
                type: "POST",
                data: JSON.stringify(data),
                dataType: "json",
                contentType: "application/json;charset=UTF-8",
                beforeSend: function () {
                    $('#submit_new_ioc').text('Saving data..')
                        .attr("disabled", true)
                        .removeClass('bt-outline-success')
                        .addClass('btn-success', 'text-dark');
                },
                complete: function () {
                    $('#submit_new_ioc')
                        .attr("disabled", false)
                        .addClass('bt-outline-success')
                        .removeClass('btn-success', 'text-dark');
                },
                success: function (data) {
                    if (data.status == 'success') {
                        swal("Done !",
                            data.message,
                            {
                                icon: "success",
                                timer: 500
                            }
                        ).then((value) => {
                            reload_iocs();
                            $('#modal_add_ioc').modal('hide');

                        });
                    } else {
                        $('#submit_new_ioc').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    if (error.responseJSON.message != '') {
                        $('#ioc-invalid-msg').text(error.responseJSON.message);
                        $('#ioc-invalid-msg').show();
                        $('#submit_new_ioc').text('Save again');
                    } else {
                        $('#submit_new_ioc').text('Save');
                    }
                    propagate_form_api_errors(error.responseJSON.data);
                }
            });
        
            return false;
        })
    });
    $('#modal_add_ioc').modal({ show: true });
}

/* Retrieve the list of iocs and build a datatable for each type of ioc */
function get_case_ioc() {
    show_loader();
    $.ajax({
        url: "/case/ioc/list" + case_param(),
        type: "GET",
        dataType: 'json',
        success: function (response) {
            if (response.status == 'success') {
                if (response.data != null) {
                    jsdata = response.data;
                    Table.clear();
                    Table.rows.add(jsdata.ioc);

                    Table.columns.adjust().draw();

                    set_last_state(jsdata.state);
                    hide_loader();
                    $('#ioc_table_wrapper').on('click', function(e){
                        if($('.popover').length>1)
                            $('.popover').popover('hide');
                            $(e.target).popover('toggle');
                        });


                    $('#ioc_table_filter').addClass('mt--4');

                    $('#ioc_table_wrapper').show();
                    $('[data-toggle="popover"]').popover();
                    Table.columns.adjust().draw();
                    load_menu_mod_options('ioc', Table);

                } else {
                    Table.clear().draw();
                    swal("Oh no !", data.message, "error")
                }
            } else {
                Table.clear().draw()
            }
        },
        error: function (error) {
            notify_error(error.statusText);
        }
    });
}

/* Edit an ioc */
function edit_ioc(ioc_id) {
    url = 'ioc/' + ioc_id + '/modal' + case_param();
    $('#modal_add_ioc_content').load(url, function () {
        load_menu_mod_options_modal(ioc_id, 'ioc', $("#ioc_modal_quick_actions"));
    });
    $('#modal_add_ioc').modal({ show: true });
}

/* Update an ioc */
function update_ioc(ioc_id) {
    if(!$('form#form_new_ioc').valid()) {
        return false;
    }

    var data = $('#form_new_ioc').serializeObject();
    data['ioc_tags'] = $('#ioc_tags').val();
    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}

    data['custom_attributes'] = attributes;

    $.ajax({
        url: 'ioc/update/' + ioc_id + case_param(),
        type: "POST",
        data: JSON.stringify(data),
        dataType: "json",
        contentType: "application/json;charset=UTF-8",
        success: function (data) {
            if (data.status == 'success') {
                swal("You're set !",
                    "The IOC has been updated successfully",
                    {
                        icon: "success",
                        timer: 500
                    }
                ).then((value) => {
                    reload_iocs();
                    $('#modal_add_ioc').modal('hide');
                });

            } else {
                $('#submit_new_ioc').text('Save again');
                swal("Oh no !", data.message, "error")
            }
        },
        error: function (error) {
            if (error.responseJSON.message != '') {
                $('#ioc-invalid-msg').text(error.responseJSON.message);
                $('#ioc-invalid-msg').show();
                $('#submit_new_ioc').text('Save again');
            } else {
                $('#submit_new_ioc').text('Save');
            }
            propagate_form_api_errors(error.responseJSON.data);
        }
    });
}

/* Delete an ioc */
function delete_ioc(ioc_id) {
    $.ajax({
        url: 'ioc/delete/' + ioc_id + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                swal("Good !",
                    "The ioc has been deleted successfully",
                    {
                        icon: "success",
                        timer: 500
                    }
                ).then((value) => {
                    reload_iocs();
                    $('#modal_add_ioc').modal('hide');
                });

            } else {
                swal("Oh no !", data.message, "error")
            }
        },
        error: function (error) {
            swal("Oh no !", error.statusText, "error")
        }
    });
}

function fire_upload_iocs() {
    $('#modal_upload_ioc').modal('show');
}

function upload_ioc() {

    var file = $("#input_upload_ioc").get(0).files[0];
    var reader = new FileReader();
    reader.onload = function (e) {
        fileData = e.target.result
        var data = new Object();
        data['csrf_token'] = $('#csrf_token').val();
        data['CSVData'] = fileData;
        $.ajax({
            url: '/case/ioc/upload' + case_param(),
            type: "POST",
            data: JSON.stringify(data),
            contentType: "application/json;charset=UTF-8",
            dataType: "json",
            success: function (data) {
                jsdata = data;
                if (jsdata.status == "success") {
                    reload_iocs();
                    $('#modal_upload_ioc').modal('hide');
                    swal("Got news for you", data.message, "success");

                } else {
                    swal("Got bad news for you", data.message, "error");
                }
            },
            error: function (error) {
                notify_error(error.responseJSON.message);
                propagate_form_api_errors(error.responseJSON.data);
            }
        });
    };
    reader.readAsText(file)

    return false;
}

function generate_sample_csv(){
    csv_data = "ioc_value,ioc_type,ioc_description,ioc_tags,ioc_tlp\n"
    csv_data += "1.1.1.1,ip-dst,Cloudflare DNS IP address,Cloudflare|DNS,green\n"
    csv_data += "wannacry.exe,filename,Wannacry sample found,Wannacry|Malware|PE,amber"
    download_file("sample_iocs.csv", "text/csv", csv_data);
}

function download_file(filename, contentType, data) {
    var element = document.createElement('a');
    element.setAttribute('href', 'data:' + contentType + ';charset=utf-8,' + encodeURIComponent(data));
    element.setAttribute('download', filename);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
}

/* Page is ready, fetch the iocs of the case */
$(document).ready(function(){
    get_case_ioc();
    setInterval(function() { check_update('ioc/state'); }, 3000);

    shared_id = getSharedLink();
    if (shared_id) {
        edit_ioc(shared_id);
    }
});