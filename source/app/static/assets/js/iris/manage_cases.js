/*************************
 *  Case creation section 
 *************************/

/* Onrefresh handler */
function onRefresh() {
    $("#update_pipeline_selector").selectpicker({
        liveSearch: true,
        style: "btn-outline-white"
        })
    $("#update_pipeline_selector").selectpicker("val", "");
    $('#update_pipeline_selector').selectpicker("refresh");
    $(".control-update-pipeline-args ").hide();
    $('.control-update-pipeline-'+ $('#update_pipeline_selector').val() ).show();
}
window.onbeforeunload = onRefresh;

/* Hide the args selectors */
$("#update_pipeline_selector").selectpicker({
    liveSearch: true,
    style: "btn-outline-white"
    })
$('#update_pipeline_selector').selectpicker("refresh");
$(".control-update-pipeline-args ").hide();
$('.control-update-pipeline-'+ $('#update_pipeline_selector').val() ).show();


/* create the select picker for customer */
$('#case_customer').selectpicker({
    liveSearch: true,
    title: "Customer",
    style: "btn-outline-white"
});

$('#update_pipeline_selector').on('change', function(e){
  $(".control-update-pipeline-args ").hide();
  $('.control-update-pipeline-'+this.value).show();
});


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

    post_request_api('/manage/cases/add', JSON.stringify(data_sent), true, function () {
        $('#submit_new_case_btn').text('Checking data..')
            .attr("disabled", true)
            .removeClass('bt-outline-success')
            .addClass('btn-success', 'text-dark');
    })
    .done((data) => {
        if (notify_auto_api(data, true)) {
            swal("That's done !",
                "Case has been successfully created",
                "success",
                {
                    buttons: {
                        again: {
                            text: "Create a case again",
                            value: "again",
                            dangerMode: true
                        },
                        dash: {
                            text: "Go to dashboard",
                            value: "dash",
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

                    default:
                        window.location.replace("/dashboard" + case_param());
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

    return false;
};

/*************************
 *  Case update section 
 *************************/
/* Dropzone creation for update */
Dropzone.autoDiscover = false;
var dropUpdate = new Dropzone("div#files_drop_1", {
    url: "cases/upload_files" + case_param(),
    acceptedFiles: ".zip,.7z,.tar.gz,.tgz,.evtx,.evtx_data,.txt,.ml",
    addRemoveLinks: true,
    autoProcessQueue: false,
    parallelUploads: 40,
    maxFiles: 40,
    maxFilesize: 10000,
    timeout: 0,
    complete: function () {
        if (this.getUploadingFiles().length === 0 && this.getQueuedFiles().length === 0) {
            $('#submit_update_case').text('Notifying for new import')
            send_update_case_data();
        }
    },
    error: function(jqXHR) {
        if(jqXHR.responseJSON) {
            notify_error(jqXHR.responseJSON.message);
        } else {
            ajax_notify_error(jqXHR, this.url);
        }
    }
});

/* Add of field for file upload */
dropUpdate.on('sending', function (file, xhr, formData) {
    formData.append('is_update', true);
    formData.append('pipeline', $('#update_pipeline_selector').val() );
    formData.append('csrf_token', $('#csrf_token').val());
});

/* Update case function. start the update task */

function send_update_case_data() {

    /* Get the pipeline args */
    var args = Object();
    $.each($(".update-" + $('#update_pipeline_selector').val()), function(el, k) {
        args['args_' + k.id] = k.value;
    });
    args['pipeline'] = $('#update_pipeline_selector').val();
    args['csrf_token'] = $('#csrf_token').val();

    post_request_api('/manage/cases/update', JSON.stringify(args), true, function () {
        $('#submit_update_case').text('Starting update');
         $('#submit_update_case')
            .attr("disabled", true)
            .addClass('bt-outline-success')
            .removeClass('btn-success', 'text-dark');
    })
    .done((data) => {
        if (notify_auto_api(data, true)) {
            $('#submit_update_case').text('Saved');
            swal("That's done !",
                "Additional files are being imported in background.\nYou can follow the progress on the dashboard.",
                "success",
                {
                    buttons: {
                        again: {
                            text: "Import files again",
                            value: "again",
                            dangerMode: true
                        },
                        dash: {
                            text: "Go to dashboard",
                            value: "dash",
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

                    default:
                        window.location.replace("/dashboard" + case_param());
                }
            });
        } else {
            $('#submit_update_case').text('Save');
            mdata = ""
            for (element in data.data) {
                mdata += data.data[element]
            }
            $.notify({
                icon: 'flaticon-error',
                title: data.message,
                message: mdata
            }, {
                type: 'danger',
                placement: {
                    from: 'top',
                    align: 'right'
                },
                time: 5000,
            });
            swal("Oh no !", data.message, "error")
        }
    })
    .fail(() => {
        $('#submit_new_case_btn').text('Save');
    })
    .always(() => {
        $('#submit_update_case')
        .attr("disabled", false)
        .addClass('bt-outline-success')
        .removeClass('btn-success', 'text-dark');
    });
}

/* Event listener to process update queue */
function submit_update_casefn() {

    var dse = $(".update-" + $('#update_pipeline_selector').val());
    for (var elm=0; elm < $(dse).length; elm++) {
        if($(dse[elm]).find('input').attr('required')) {
            if ( ! $(dse[elm]).find('input').val() ) {
                notify_error("Required fields are not set");
                return false;
            }
        }
    }

    dropUpdate.processQueue();
}

 /*************************
 *  Case list section 
 *************************/
/* case table creation */
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
    "order": [[3, "desc"]],
    "autoWidth": false,
    "columns": [
        {
            "render": function (data, type, row) {
                data = sanitizeHTML(data);
                return '<a href="#" onclick="case_detail(\'' + row['case_id'] + '\');">' + decodeURIComponent(data) + '</a>';
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
    ]
});

/* Refresh case table function */
function refresh_case_table() {
    $('#cases_table').DataTable().ajax.reload();
    $('#cases_table').DataTable().columns.adjust().draw();
    notify_success("Refreshed");
}

/* Create detail modal function */
function case_detail(id) {
    url = 'cases/details/' + id + case_param();
    $('#info_case_modal_content').load(url, function () {
        $('#modal_case_detail').modal({ show: true });
    });
}

/* Remove case function */
function remove_case(id) {

    swal({
        title: "Are you sure?",
        text: "You won't be able to revert this !\nAll associated data will be deleted",
        icon: "warning",
        buttons: true,
        dangerMode: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, delete it!'
    })
        .then((willDelete) => {
            if (willDelete) {
                get_request_api('/manage/cases/delete/' + id)
                .done((data) => {
                    if (notify_auto_api(data)) {
                        refresh_case_table();
                        $('#modal_case_detail').modal('hide');
                    }
                });
            } else {
                swal("Pfew, that's was close");
            }
        });
}

/* Reopen case function */
function reopen_case(id) {
    get_request_api('/manage/cases/reopen/' + id)
    .done((data) => {
        refresh_case_table();
        $('#modal_case_detail').modal('hide');
    });
}

/* Close case function */
function close_case(id) {
    swal({
        title: "Are you sure?",
        text: "Case ID " + id + " will be closed and will not appear in contexts anymore",
        icon: "warning",
        buttons: true,
        dangerMode: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, close it!'
    })
    .then((willClose) => {
        if (willClose) {
            get_request_api('/manage/cases/close/' + id)
            .done((data) => {
                refresh_case_table();
                $('#modal_case_detail').modal('hide');
            });
        }
    });
}


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