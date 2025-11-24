/* reload the artifact table */
var g_artifact_id = null;
var g_artifact_desc_editor = null;


function reload_artifacts() {
    get_case_artifact();
}

function edit_in_artifact_desc() {
    if($('#container_artifact_desc_content').is(':visible')) {
        $('#container_artifact_description').show(100);
        $('#container_artifact_desc_content').hide(100);
        $('#artifact_edition_btn').hide(100);
        $('#artifact_preview_button').hide(100);
    } else {
        $('#artifact_preview_button').show(100);
        $('#artifact_edition_btn').show(100);
        $('#container_artifact_desc_content').show(100);
        $('#container_artifact_description').hide(100);
    }
}

/* Fetch a modal that is compatible with the requested artifact type */ 
function add_artifact() {
    url = 'artifact/add/modal' + case_param();

    $('#modal_add_artifact_content').load(url, function (response, status, xhr) {
        hide_minimized_modal_box();
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        g_artifact_desc_editor = get_new_ace_editor('artifact_description', 'artifact_desc_content', 'target_artifact_desc',
                            function() {
                                $('#last_saved').addClass('btn-danger').removeClass('btn-success');
                                $('#last_saved > i').attr('class', "fa-solid fa-file-circle-exclamation");
                            }, null);

        g_artifact_desc_editor.setOption("minLines", "10");
        edit_in_artifact_desc();

        headers = get_editor_headers('g_artifact_desc_editor', null, 'artifact_edition_btn');
        $('#artifact_edition_btn').append(headers);


        $('#submit_new_artifact').on("click", function () {
            if(!$('form#form_new_artifact').valid()) {
                return false;
            }

            var data = $('#form_new_artifact').serializeObject();
            data['artifact_tags'] = $('#artifact_tags').val();
            data['artifact_description'] = g_artifact_desc_editor.getValue();

            ret = get_custom_attributes_fields();
            has_error = ret[0].length > 0;
            attributes = ret[1];

            if (has_error){return false;}

            data['custom_attributes'] = attributes;

            id = $('#artifact_id').val();
            
            if ($('#artifact_one_per_line').is(':checked')) {
                let artifacts_values = $('#artifact_value').val();
                let artifacts_list = artifacts_values.split(/\r?\n/);
                for (let index in artifacts_list) {
                    if (artifacts_list[index] === '' || artifacts_list[index] === '\n') {
                        continue;
                    }

                    data['artifact_value'] = artifacts_list[index];
                    post_request_api('artifact/add', JSON.stringify(data), true, function () {
                        $('#submit_new_artifact').text('Saving data..')
                            .attr("disabled", true)
                            .removeClass('bt-outline-success')
                            .addClass('btn-success', 'text-dark');
                    })
                    .done((data) => {
                        if (data.status == 'success') {
                                reload_artifacts();
                                notify_success(data.message);
                                if (index == (artifacts_list.length - 1)) {
                                    $('#modal_add_artifact').modal('hide');
                                }
                        } else {
                            $('#submit_new_artifact').text('Save again');
                            swal("Oh no !", data.message, "error")
                        }
                    })
                    .always(function () {
                        $('#submit_new_artifact')
                            .attr("disabled", false)
                            .addClass('bt-outline-success')
                            .removeClass('btn-success', 'text-dark');
                    })
                }
            }

            else {
                post_request_api('artifact/add', JSON.stringify(data), true, function () {
                        $('#submit_new_artifact').text('Saving data..')
                            .attr("disabled", true)
                            .removeClass('bt-outline-success')
                            .addClass('btn-success', 'text-dark');
                    })
                .done((data) => {
                    if (data.status == 'success') {
                            reload_artifacts();
                            notify_success(data.message);
                            $('#modal_add_artifact').modal('hide');

                    } else {
                        $('#submit_new_artifact').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                })
                .always(function () {
                    $('#submit_new_artifact')
                        .attr("disabled", false)
                        .addClass('bt-outline-success')
                        .removeClass('btn-success', 'text-dark');
                })
            }
            return false;
        });

        $('#modal_add_artifact').modal({ show: true });
        $('#artifact_value').focus();

    });

    return false;
}

function save_artifact() {
    $('#submit_new_artifact').click();
}

/* Retrieve the list of artifacts and build a datatable for each type of artifact */
function get_case_artifact() {
    show_loader();

    get_request_api("/case/artifact/list")
    .done(function (response) {
        if (response.status == 'success') {
            if (response.data != null) {
                jsdata = response.data;
                Table.clear();
                Table.rows.add(jsdata.artifact);

                set_last_state(jsdata.state);
                $('#artifact_table_wrapper').on('click', function(e){
                    if($('.popover').length>1)
                        $('.popover').popover('hide');
                        $(e.target).popover('toggle');
                    });

                $('#artifact_table_wrapper').show();
                Table.columns.adjust().draw();
                load_menu_mod_options('artifact', Table, delete_artifact);
                hide_loader();
                Table.responsive.recalc();
                $('[data-toggle="popover"]').popover();

                $(document)
                    .off('click', '.artifact_details_link')
                    .on('click', '.artifact_details_link', function(event) {
                    event.preventDefault();
                    let artifact_id = $(this).data('artifact_id');
                    edit_artifact(artifact_id);
                });


            } else {
                Table.clear().draw();
                swal("Oh no !", data.message, "error")
            }
        } else {
            Table.clear().draw()
        }
    })
}


/* Edit an artifact */
function edit_artifact(artifact_id) {
    url = 'artifact/' + artifact_id + '/modal' + case_param();
    $('#modal_add_artifact_content').load(url, function (response, status, xhr) {
        hide_minimized_modal_box();
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        
        g_artifact_id = artifact_id;
        g_artifact_desc_editor = get_new_ace_editor('artifact_description', 'artifact_desc_content', 'target_artifact_desc',
                            function() {
                                $('#last_saved').addClass('btn-danger').removeClass('btn-success');
                                $('#last_saved > i').attr('class', "fa-solid fa-file-circle-exclamation");
                            }, null, false, false);

        g_artifact_desc_editor.setOption("minLines", "10");
        preview_artifact_description(true);
        headers = get_editor_headers('g_artifact_desc_editor', null, 'artifact_edition_btn');
        $('#artifact_edition_btn').append(headers);

        load_menu_mod_options_modal(artifact_id, 'artifact', $("#artifact_modal_quick_actions"));
        $('.dtr-modal').hide();
        $('#modal_add_artifact').modal({ show: true });
        edit_in_artifact_desc();
    });

}

function preview_artifact_description(no_btn_update) {
    if(!$('#container_artifact_description').is(':visible')) {
        artifact_desc = g_artifact_desc_editor.getValue();
        converter = get_showdown_convert();
        html = converter.makeHtml(do_md_filter_xss(artifact_desc));
        artifact_desc_html = do_md_filter_xss(html);
        $('#target_artifact_desc').html(artifact_desc_html);
        $('#container_artifact_description').show();
        if (!no_btn_update) {
            $('#artifact_preview_button').html('<i class="fa-solid fa-eye-slash"></i>');
        }
        $('#container_artifact_desc_content').hide();
    }
    else {
        $('#container_artifact_description').hide();
         if (!no_btn_update) {
            $('#artifact_preview_button').html('<i class="fa-solid fa-eye"></i>');
        }

        $('#artifact_preview_button').html('<i class="fa-solid fa-eye"></i>');
        $('#container_artifact_desc_content').show();
    }
}

function update_artifact(artifact_id) {
    update_artifact_ext(artifact_id, true);
}

function escalate_artifact(artifact_id) {
    escalate_artifact_ext(artifact_id, true);
}

/* Update an artifact */
function update_artifact_ext(artifact_id, do_close) {
    if(!$('form#form_new_artifact').valid()) {
        return false;
    }

    if (artifact_id === undefined || artifact_id === null) {
        artifact_id = g_artifact_id;
    }

    var data = $('#form_new_artifact').serializeObject();
    data['artifact_tags'] = $('#artifact_tags').val();
    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}
    data['artifact_description'] = g_artifact_desc_editor.getValue();
    data['custom_attributes'] = attributes;

    post_request_api('artifact/update/' + artifact_id, JSON.stringify(data), true)
    .done((data) => {
        if (data.status == 'success') {
            reload_artifacts();

            $('#submit_new_artifact').text("Saved").addClass('btn-outline-success').removeClass('btn-outline-danger').removeClass('btn-outline-warning');
            $('#last_saved').removeClass('btn-danger').addClass('btn-success');
            $('#last_saved > i').attr('class', "fa-solid fa-file-circle-check");

            if (do_close !== undefined && do_close === true) {
                $('#modal_add_artifact').modal('hide');
            }

            notify_success(data.message);

        } else {
            $('#submit_new_artifact').text('Save again');
            swal("Oh no !", data.message, "error")
        }
    })

}

/* Escalate an artifact */
function escalate_artifact_ext(artifact_id, do_close) {
    if(!$('form#form_new_artifact').valid()) {
        return false;
    }

    if (artifact_id === undefined || artifact_id === null) {
        artifact_id = g_artifact_id;
    }

    var data = $('#form_new_artifact').serializeObject();
    data['artifact_tags'] = $('#artifact_tags').val();
    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}
    data['artifact_description'] = g_artifact_desc_editor.getValue();
    data['custom_attributes'] = attributes;

    post_request_api('artifact/escalate/' + artifact_id, JSON.stringify(data), true)
    .done((data) => {
        if (data.status == 'success') {
            reload_artifacts();

            $('#submit_new_artifact').text("Saved").addClass('btn-outline-success').removeClass('btn-outline-danger').removeClass('btn-outline-warning');
            $('#last_saved').removeClass('btn-danger').addClass('btn-success');
            $('#last_saved > i').attr('class', "fa-solid fa-file-circle-check");

            if (do_close !== undefined && do_close === true) {
                $('#modal_add_artifact').modal('hide');
            }

            notify_success(data.message);

        } else {
            $('#submit_new_artifact').text('Save again');
            swal("Oh no !", data.message, "error")
        }
    })

}

/* Delete an artifact */
function delete_artifact(artifact_id) {
    do_deletion_prompt("You are about to delete Artifact #" + artifact_id)
    .then((doDelete) => {
        if (doDelete) {
            post_request_api('artifact/delete/' + artifact_id)
            .done((data) => {
                if (data.status == 'success') {
                    reload_artifacts();
                    notify_success(data.message);
                    $('#modal_add_artifact').modal('hide');

                } else {
                    swal("Oh no !", data.message, "error")
                }
            })
        }
    });
}

function fire_upload_artifacts() {
    $('#modal_upload_artifact').modal('show');
}

function upload_artifact() {

    var file = $("#input_upload_artifact").get(0).files[0];
    var reader = new FileReader();
    reader.onload = function (e) {
        fileData = e.target.result
        var data = new Object();
        data['csrf_token'] = $('#csrf_token').val();
        data['CSVData'] = fileData;

        post_request_api('/case/artifact/upload', JSON.stringify(data), true)
        .done((data) => {
            jsdata = data;
            if (jsdata.status == "success") {
                reload_artifacts();
                $('#modal_upload_artifact').modal('hide');
                swal("Got news for you", data.message, "success");

            } else {
                swal("Got bad news for you", data.message, "error");
            }
        })
    };
    reader.readAsText(file)

    return false;
}

function generate_sample_csv(){
    csv_data = "artifact_value,artifact_type,artifact_description,artifact_tags,artifact_tlp\n"
    csv_data += "1.1.1.1,ip-dst,Cloudflare DNS IP address,Cloudflare|DNS,green\n"
    csv_data += "wannacry.exe,filename,Wannacry sample found,Wannacry|Malware|PE,amber"
    download_file("sample_artifacts.csv", "text/csv", csv_data);
}

/* Page is ready, fetch the artifacts of the case */
$(document).ready(function(){

    /* add filtering fields for each table of the page (must be done before datatable initialization) */
    $.each($.find("table"), function(index, element){
        addFilterFields($(element).attr("id"));
    });

    Table = $("#artifact_table").DataTable({
        dom: '<"container-fluid"<"row"<"col"l><"col"f>>>rt<"container-fluid"<"row"<"col"i><"col"p>>>',
        fixedHeader: true,
        aaData: [],
        aoColumns: [
          {
            "data": "artifact_value",
            "render": function (data, type, row, meta) {
                if (type === 'display') {

                    let datak = '';
                    let anchor = $('<a>')
                        .attr('href', 'javascript:void(0);')
                        .attr('data-artifact_id', row['artifact_id'])
                        .attr('title', `Artifact ID #${row['artifact_id']} - ${data}`)
                        .addClass('artifact_details_link')

                    if (isWhiteSpace(data) || data === null) {
                        datak = '#' + row['artifact_id'];
                        anchor.text(datak);
                    } else {
                        datak= ellipsis_field(data, 64);
                        anchor.html(datak);
                    }

                    return anchor.prop('outerHTML');
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
          { "data": "artifact_description",
           "render": function (data, type, row, meta) {
              if (type === 'display') {
                  return ret_obj_dt_description(data);
              }
              return data;
            }
          },
          { "data": "artifact_tags",
            "render": function (data, type, row, meta) {
              if (type === 'display' && data != null) {
                  let tags = "";
                  let de = data.split(',');
                  for (let tag in de) {
                      tags += get_tag_from_data(de[tag], 'badge badge-light ml-2');
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
              } else if (type === 'export' && data != null) {
                  return data.map(ds => sanitizeHTML(ds['case_name'])).join(',');
                }
              return data;
            }
          },
          {
            "data": "tlp_name",
            "render": function(data, type, row, meta) {
               if (type === 'display') {
                    if (data) {
                        data = sanitizeHTML(data);
                        data = '<span class="badge badge-' + row['tlp_bscolor'] + ' ml-2">tlp:' + data + '</span>';
                    } else {
                        return `<span class="badge badge-light ml-2">unspecified</span>`
                    }
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
                display: $.fn.dataTable.Responsive.display.childRow,
                renderer: $.fn.dataTable.Responsive.renderer.tableAll()
            }
        },
        buttons: [],
        orderCellsTop: true,
        initComplete: function () {
            tableFiltering(this.api(), 'artifact_table');
        },
        select: true
    });
    $("#artifact_table").css("font-size", 12);

    Table.on( 'responsive-resize', function ( e, datatable, columns ) {
            hide_table_search_input( columns );
    });

    var buttons = new $.fn.dataTable.Buttons(Table, {
     buttons: [
        { "extend": 'csvHtml5', "text":'<i class="fas fa-cloud-download-alt"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Download as CSV', "exportOptions": { "columns": ':visible', 'orthogonal':  'export' } } ,
        { "extend": 'copyHtml5', "text":'<i class="fas fa-copy"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Copy', "exportOptions": { "columns": ':visible', 'orthogonal':  'export' } },
        { "extend": 'colvis', "text":'<i class="fas fa-eye-slash"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Toggle columns' }
    ]
}).container().appendTo($('#tables_button'));

    get_case_artifact();
    setInterval(function() { check_update('artifact/state'); }, 3000);

    shared_id = getSharedLink();
    if (shared_id) {
        edit_artifact(shared_id);
    }
});