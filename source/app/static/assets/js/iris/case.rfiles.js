/* reload the rfiles table */
function reload_rfiles(notify) {
    get_case_rfiles();
    if (notify !== undefined) {
        notify_success("Refreshed");
    }
}

function edit_in_evidence_desc() {
    if($('#container_evidence_desc_content').is(':visible')) {
        $('#container_evidence_description').show(100);
        $('#container_evidence_desc_content').hide(100);
        $('#evidence_edition_btn').hide(100);
        $('#evidence_preview_button').hide(100);
    } else {
        $('#evidence_preview_button').show(100);
        $('#evidence_edition_btn').show(100);
        $('#container_evidence_desc_content').show(100);
        $('#container_evidence_description').hide(100);
    }
}

function get_hash() {
    if (document.getElementById("input_autofill").files[0] === undefined) {
        $('#btn_rfile_proc').text("Please select a file");
        return;
    }
    getMD5(
        document.getElementById("input_autofill").files[0],
        prog => $('#btn_rfile_proc').text("Processing "+ (prog * 100).toFixed(2) + "%")
    ).then(
        res => on_done_hash(res),
        err => console.error(err)
    );
}

function on_done_hash(result) {
    $('#btn_rfile_proc').text('Done processing');
    $('form#form_edit_rfile #file_hash').val(result);
    $('form#form_edit_rfile #filename').val(document.getElementById("input_autofill").files[0].name);
    $('form#form_edit_rfile #file_size').val(document.getElementById("input_autofill").files[0].size);
}

function add_modal_rfile() {
    url = 'evidences/add/modal' + case_param();
    $('#modal_add_rfiles_content').load(url, function (response, status, xhr) {
        hide_minimized_modal_box();
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        g_evidence_desc_editor = get_new_ace_editor('evidence_description', 'evidence_desc_content', 'target_evidence_desc',
                    function() {
                        $('#last_saved').addClass('btn-danger').removeClass('btn-success');
                        $('#last_saved > i').attr('class', "fa-solid fa-file-circle-exclamation");
                    }, null);
        g_evidence_desc_editor.setOption("minLines", "10");
        edit_in_evidence_desc();

        let headers = get_editor_headers('g_evidence_desc_editor', null, 'evidence_edition_btn');
        $('#evidence_edition_btn').append(headers);

        load_evidence_type();
        
        $('#modal_add_rfiles').modal({ show: true });
        $('#filename').focus();
    });
}

function add_rfile() {
    let data_sent = $('form#form_edit_rfile').serializeObject();
    data_sent['csrf_token'] = $('#csrf_token').val();
    data_sent['file_description'] = g_evidence_desc_editor.getValue();
    data_sent['type_id'] = $('#file_type_id').val();

    let sd = $('#start_date').val();
    let st = $('#start_time').val()
    if (sd && st) {
        data_sent['start_date'] = `${sd}T${st}`;
    }

    let ed = $('#end_date').val();
    let et = $('#end_time').val();
    if (ed && et) {
        data_sent['end_date'] = `${ed}T${et}`;
    }

    let ret = get_custom_attributes_fields();
    let has_error = ret[0].length > 0;
    let attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;

    post_request_api('/case/evidences/add', JSON.stringify(data_sent), true)
    .done((data) => {
        notify_auto_api(data);
        get_case_rfiles();
        $('#modal_add_rfiles').modal("hide");
    });

    return false;
}

function readChunked(file, chunkCallback, endCallback) {
  var fileSize   = file.size;
  var chunkSize  = 4 * 1024 * 1024; // 4MB
  var offset     = 0;

  var reader = new FileReader();
  reader.onload = function() {
    if (reader.error) {
      endCallback(reader.error || {});
      return;
    }
    offset += reader.result.length;
    // callback for handling read chunk
    // TODO: handle errors
    chunkCallback(reader.result, offset, fileSize);
    if (offset >= fileSize) {
      endCallback(null);
      return;
    }
    readNext();
  };

  reader.onerror = function(err) {
    endCallback(err || {});
  };

  function readNext() {
    var fileSlice = file.slice(offset, offset + chunkSize);
    reader.readAsBinaryString(fileSlice);
  }
  readNext();
}

function getMD5(blob, cbProgress) {
  return new Promise((resolve, reject) => {
    var md5 = CryptoJS.algo.MD5.create();
    readChunked(blob, (chunk, offs, total) => {
      md5.update(CryptoJS.enc.Latin1.parse(chunk));
      if (cbProgress) {
        cbProgress(offs / total);
      }
    }, err => {
      if (err) {
        reject(err);
      } else {
        // TODO: Handle errors
        var hash = md5.finalize();
        var hashHex = hash.toString(CryptoJS.enc.Hex);
        resolve(hashHex);
      }
    });
  });
}

/* Retrieve the list of rfiles and build a datatable for each type of rfiles */
function get_case_rfiles() {

    get_request_api("/case/evidences/list")
    .done(function (response) {
        if (response.status == 'success') {
            if (response.data != null) {
                jsdata = response.data;
                Table.clear();
                Table.rows.add(jsdata.evidences);
                Table.columns.adjust().draw();

                load_menu_mod_options('evidence', Table, delete_rfile);

                set_last_state(jsdata.state);
                hide_loader();

                $('#rfiles_table_wrapper').show();
                Table.responsive.recalc();

                $(document)
                    .off('click', '.evidence_details_link')
                    .on('click', '.evidence_details_link', function(event) {
                    event.preventDefault();
                    let evidence_id = $(this).data('evidence_id');
                    edit_rfiles(evidence_id);
                });

            } else {
                Table.clear().draw();
                swal("Oh no !", data.message, "error")
            }
        } else {
            Table.clear().draw()
        }
    });

}

/* Edit an rfiles */
function edit_rfiles(rfiles_id) {
    url = 'evidences/' + rfiles_id + '/modal' + case_param();
    $('#modal_add_rfiles_content').load(url, function (response, status, xhr) {
        hide_minimized_modal_box();
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        g_evidence_desc_editor = get_new_ace_editor('evidence_description', 'evidence_desc_content', 'target_evidence_desc',
                            function() {
                                $('#last_saved').addClass('btn-danger').removeClass('btn-success');
                                $('#last_saved > i').attr('class', "fa-solid fa-file-circle-exclamation");
                                $('#submit_new_evidence').text("Unsaved").removeClass('btn-success').addClass('btn-outline-warning').removeClass('btn-outline-danger');
                            }, null);

        g_evidence_desc_editor.setOption("minLines", "6");
        preview_evidence_description(true);

        let headers = get_editor_headers('g_evidence_desc_editor', null, 'evidence_edition_btn');
        $('#evidence_edition_btn').append(headers);
        
        load_menu_mod_options_modal(rfiles_id, 'evidence', $("#evidence_modal_quick_actions"));

        load_evidence_type();
        
        $('#modal_add_rfiles').modal({ show: true });

        edit_in_evidence_desc();
    });
}

function show_x_time_converter(item){
    $(`#${item}_date_convert`).show();
    $(`#${item}_date_convert_input`).focus();
    $(`#${item}_date_inputs`).hide();
}

function hide_x_time_converter(item){
    $(`#${item}_date_convert`).hide();
    $(`#${item}_date_inputs`).show();
    $(`#${item}_date`).focus();
}


function time_converter(item){
    let date_val = $(`#${item}_date_convert_input`).val();

    let data_sent = Object();
    data_sent['date_value'] = date_val;
    data_sent['csrf_token'] = $('#csrf_token').val();

    post_request_api('timeline/events/convert-date', JSON.stringify(data_sent))
    .done(function(data) {
        if(notify_auto_api(data)) {
            $(`#${item}_date`).val(data.data.date);
            $(`#${item}_time`).val(data.data.time);
            $(`#${item}_tz`).val(data.data.tz);
            hide_x_time_converter(item);
            $(`#convert_bad_feedback_${item}`).text('');
        }
    })
    .fail(function() {
        $(`#convert_bad_feedback_${item}`).text('Unable to find a matching pattern for the date');
    });
}


function load_evidence_type() {
    get_request_api('/manage/evidence-types/list')
    .done((data) => {
        if(notify_auto_api(data, true)) {
            let ftype = $('#file_type_id');
            if (data.data != null) {
                let options = data.data;
                for (let idx in options) {
                    ftype.append(`<option value="${options[idx].id}">${filterXSS(options[idx].name)}</option>`);
                }
                ftype.selectpicker({
                    liveSearch: true,
                    title: "Evidence type"
                });
                let stored_type_id = $('#store_type_id').data('file-type-id');
                if (stored_type_id !== undefined || stored_type_id !== "") {
                    ftype.selectpicker('val', stored_type_id);
                    ftype.selectpicker('refresh');
                }
            }

        }
    })
}

function preview_evidence_description(no_btn_update) {
    if(!$('#container_evidence_description').is(':visible')) {
        evidence_desc = g_evidence_desc_editor.getValue();
        converter = get_showdown_convert();
        html = converter.makeHtml(do_md_filter_xss(evidence_desc));
        evidence_desc_html = do_md_filter_xss(html);
        $('#target_evidence_desc').html(evidence_desc_html);
        $('#container_evidence_description').show();
        if (!no_btn_update) {
            $('#evidence_preview_button').html('<i class="fa-solid fa-eye-slash"></i>');
        }
        $('#container_evidence_desc_content').hide();
    }
    else {
        $('#container_evidence_description').hide();
         if (!no_btn_update) {
            $('#evidence_preview_button').html('<i class="fa-solid fa-eye"></i>');
        }

        $('#evidence_preview_button').html('<i class="fa-solid fa-eye"></i>');
        $('#container_evidence_desc_content').show();
    }
}

/* Update an rfiles */
function update_rfile(rfiles_id) {
    let data_sent = $('form#form_edit_rfile').serializeObject();
    data_sent['csrf_token'] = $('#csrf_token').val();
    data_sent['type_id'] = $('#file_type_id').val();
    let sd = $('#start_date').val();
    let st = $('#start_time').val()
    if (sd && st) {
        data_sent['start_date'] = `${sd}T${st}`;
    }

    let ed = $('#end_date').val();
    let et = $('#end_time').val();
    if (ed && et) {
        data_sent['end_date'] = `${ed}T${et}`;
    }


    let ret = get_custom_attributes_fields();
    let has_error = ret[0].length > 0;
    let attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;
    data_sent['file_description'] = g_evidence_desc_editor.getValue();

    post_request_api('evidences/update/' + rfiles_id, JSON.stringify(data_sent), true)
    .done((data) => {
        notify_auto_api(data);
        reload_rfiles();
        $('#modal_add_rfiles').modal("hide");
    });
}

/* Delete an rfiles */
function delete_rfile(rfiles_id) {
    do_deletion_prompt("You are about to delete evidence #" + rfiles_id)
    .then((doDelete) => {
        if (doDelete) {
            post_request_api('evidences/delete/' + rfiles_id)
            .done(function(data){
               reload_rfiles();
               $('#modal_add_rfiles').modal('hide');
               notify_auto_api(data);
            });
        }
    });
}

/* Page is ready, fetch the rfiles of the case */
$(document).ready(function(){

    /* add filtering fields for each table of the page (must be done before datatable initialization) */
    $.each($.find("table"), function(index, element){
        addFilterFields($(element).attr("id"));
    });

    Table = $("#rfiles_table").DataTable({
        dom: '<"container-fluid"<"row"<"col"l><"col"f>>>rt<"container-fluid"<"row"<"col"i><"col"p>>>',
        fixedHeader: true,
        aaData: [],
        aoColumns: [
          {
            "data": "filename",
            "render": function (data, type, row, meta) {
              if (type === 'display' && data != null) {

                    let datak = '';
                    let anchor = $('<a>')
                        .attr('href', 'javascript:void(0);')
                        .attr('data-evidence_id', row['id'])
                        .attr('title', `Evidence ID #${row['id']} - ${data}`)
                        .addClass('evidence_details_link')

                    if (isWhiteSpace(data)) {
                        datak = '#' + row['id'];
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
          { "data": "type_id",
            "render": function (data, type, row, meta) {
              if (type === 'display' || type === 'sort' || type === 'filter') {

                  if (row['type'] !== null && row['type'] !== undefined) {
                      data = sanitizeHTML(row['type'].name)
                  } else {
                      data = 'Unspecified'
                  }
              }
              return data;
            }
          },
          { "data": "file_hash",
            "render": function (data, type, row, meta) {
                if (type === 'display') { return ret_obj_dt_description(data);}
                return data;
              }
          },
          { "data": "file_size",
            "render": function (data, type, row, meta) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
              }},
          { "data": "file_description",
            "render": function (data, type, row, meta) {
                if (type === 'display') { return ret_obj_dt_description(data);}
                return data;
              }},
          { "data": "user",
            "render": function (data, type, row, meta) {
                if (type === 'display'|| type === 'sort' || type === 'filter') {
                    data = sanitizeHTML(data.user_name);
                }
                return data;
              }}
        ],
        filter: true,
        info: true,
        ordering: true,
        processing: true,
        retrieve: true,
        buttons: [
        ],
        responsive: {
            details: {
                display: $.fn.dataTable.Responsive.display.childRow,
                renderer: $.fn.dataTable.Responsive.renderer.tableAll()
            }
        },
        orderCellsTop: true,
        initComplete: function () {
            tableFiltering(this.api(), 'rfiles_table');
        },
        select: true
    });
    $("#rfiles_table").css("font-size", 12);
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

    Table.on( 'responsive-resize', function ( e, datatable, columns ) {
            hide_table_search_input( columns );
    });

    get_case_rfiles();
    setInterval(function() { check_update('evidences/state'); }, 3000);

    /* Modal to add rfiles is closed, clear its contents */
    $('.modal').on('hidden.bs.modal', function () {
        $(this).find('form').trigger('reset');
        $('#btn_rfile_proc').text('Process');
    })

    shared_id = getSharedLink();
    if (shared_id) {
        edit_rfiles(shared_id);
    }

});
