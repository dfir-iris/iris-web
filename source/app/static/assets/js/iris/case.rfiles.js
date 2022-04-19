/* reload the rfiles table */
function reload_rfiles() {
    get_case_rfiles();
    notify_success("Refreshed");
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
    $('#modal_add_rfiles_content').load(url, function () {});
    $('#modal_add_rfiles').modal({ show: true });
}

function add_rfile() {
    var data_sent = $('form#form_edit_rfile').serializeObject();
    data_sent['csrf_token'] = $('#csrf_token').val();
    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;

    $.ajax({
        url: '/case/evidences/add' + case_param(),
        type: "POST",
        data: JSON.stringify(data_sent),
        contentType: "application/json;charset=UTF-8",
        dataType: "json",
        success: function (data) {
            jsdata = data;
            if (jsdata.status == "success") {
                if (typeof reload_rfiles != "undefined") { reload_rfiles(); }
                $('#modal_add_rfiles').modal('hide');
                notify_success("File registered");

            } else {
                notify_error("Unable to register file. " + jsdata.message)
            }
        },
        error: function (error) {
            notify_error(error.responseJSON.message);
            propagate_form_api_errors(error.responseJSON.data);
        }
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

/* add filtering fields for each table of the page (must be done before datatable initialization) */
$.each($.find("table"), function(index, element){
    addFilterFields($(element).attr("id"));
});

Table = $("#rfiles_table").DataTable({
    dom: 'Blfrtip',
    aaData: [],
    aoColumns: [
      {
        "data": "filename",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
            if (isWhiteSpace(data)) {
                data = '#' + row['id'];
            } else {
                data = sanitizeHTML(data);
            }
            share_link = buildShareLink(row['id']);
            data = '<a data-toggle="tooltip" data-selector="true" href="' + share_link + '" title="Evidence ID #' + row['id'] + '" onclick="edit_rfiles(\'' + row['id'] + '\');return false;">' + data +'</a>';
          }
          return data;
        }
      },
      { "data": "date_added" },
      { "data": "file_hash",
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
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
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }},
      { "data": "username",
        "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
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
    orderCellsTop: true,
    initComplete: function () {
        tableFiltering(this.api());
    },
    select: true
});
$("#rfiles_table").css("font-size", 12);
var buttons = new $.fn.dataTable.Buttons(Table, {
     buttons: [
        { "extend": 'csvHtml5', "text":'<i class="fas fa-cloud-download-alt"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Download as CSV' },
        { "extend": 'copyHtml5', "text":'<i class="fas fa-copy"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Copy' },
    ]
}).container().appendTo($('#tables_button'));

/* Retrieve the list of rfiles and build a datatable for each type of rfiles */
function get_case_rfiles() {
    $.ajax({
        url: "/case/evidences/list" + case_param(),
        type: "GET",
        dataType: 'json',
        success: function (response) {
            if (response.status == 'success') {
                if (response.data != null) {
                    jsdata = response.data;
                    Table.clear();
                    Table.rows.add(jsdata.evidences);
                    Table.columns.adjust().draw();

                    load_menu_mod_options('evidence', Table);

                    set_last_state(jsdata.state);
                    hide_loader();

                    $('#rfiles_table_wrapper').show();

                } else {
                    Table.clear().draw();
                    swal("Oh no !", data.message, "error")
                }
            } else {
                Table.clear().draw()
            }
        },
        error: function (error) {
            swal("Oh no !", error.statusText, "error")
        }
    });
}

/* Edit an rfiles */
function edit_rfiles(rfiles_id) {
    url = 'evidences/' + rfiles_id + '/modal' + case_param();
    $('#modal_add_rfiles_content').load(url, function () {
        load_menu_mod_options_modal(rfiles_id, 'evidence', $("#evidence_modal_quick_actions"));
    });
    $('#modal_add_rfiles').modal({ show: true });
}

/* Update an rfiles */
function update_rfile(rfiles_id) {
    var data_sent = $('form#form_edit_rfile').serializeObject();
    data_sent['csrf_token'] = $('#csrf_token').val();
    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;


    $.ajax({
        url: 'evidences/update/' + rfiles_id + case_param(),
        type: "POST",
        data: JSON.stringify(data_sent),
        contentType: "application/json;charset=UTF-8",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                swal("You're set !",
                    "The file has been updated on register successfully",
                    {
                        icon: "success",
                        timer: 500
                    }
                ).then((value) => {
                    reload_rfiles();
                    $('#modal_add_rfiles').modal('hide');
                });

            } else {
                $('#submit_new_rfiles').text('Save again');
                swal("Oh no !", data.message, "error")
            }
        },
        error: function (error) {
            notify_error(error.responseJSON.message);
            propagate_form_api_errors(error.responseJSON.data);
        }
    });
}

/* Delete an rfiles */
function delete_rfile(rfiles_id) {
    $.ajax({
        url: 'evidences/delete/' + rfiles_id + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                swal("Good !",
                    "The file has been deleted from register successfully",
                    {
                        icon: "success",
                        timer: 500
                    }
                ).then((value) => {
                    reload_rfiles();
                    $('#modal_add_rfiles').modal('hide');
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

/* Modal to add rfiles is closed, clear its contents */
$('.modal').on('hidden.bs.modal', function () {
    $(this).find('form').trigger('reset');
    $('#btn_rfile_proc').text('Process');
})

/* Page is ready, fetch the rfiles of the case */
$(document).ready(function(){
    get_case_rfiles();
    setInterval(function() { check_update('evidences/state'); }, 3000);

    shared_id = getSharedLink();
    if (shared_id) {
        edit_rfiles(shared_id);
    }

});
