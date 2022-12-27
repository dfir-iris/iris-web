/*************************
 *  Case update section
 *************************/
/* Dropzone creation for update */
Dropzone.autoDiscover = false;

Dropzone.prototype.getErroredFiles = function () {
    var file, _i, _len, _ref, _results;
    _ref = this.files;
    _results = [];
    for (_i = 0, _len = _ref.length; _i < _len; _i++) {
        file = _ref[_i];
        if (file.status === Dropzone.ERROR) {
            _results.push(file);
        }
    }
    return _results;
};

var dropUpdate = new Dropzone("div#files_drop_1", {
    url: "/manage/cases/upload_files" + case_param(),
    addRemoveLinks: true,
    autoProcessQueue: false,
    parallelUploads: 40,
    maxFiles: 40,
    maxFilesize: 10000,
    timeout: 0,
    complete: function () {
        if (this.getUploadingFiles().length === 0 && this.getQueuedFiles().length === 0 && this.getErroredFiles().length === 0) {
            $('#submit_update_case').text('Notifying for new import')
            send_update_case_data();
        }
    },
    error: function(jqXHR, error) {
        if(error !== null || error !== undefined) {
            notify_error(error.message);
        } else {
            notify_error(jqXHR);
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

    post_request_api('/manage/cases/trigger-pipeline', JSON.stringify(args), true, function () {
        $('#submit_update_case').text('Starting pipeline');
         $('#submit_update_case')
            .attr("disabled", true)
            .addClass('bt-outline-success')
            .removeClass('btn-success', 'text-dark');
    })
    .done((data) => {
        if (notify_auto_api(data, true)) {
            $('#submit_update_case').text('Saved');
            swal("That's done !",
                "Files are being processed in background.\nYou can follow the progress in DIM Tasks",
                "success",
                {
                    buttons: {
                        again: {
                            text: "Import files again",
                            value: "again"
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
                        window.location.replace("/case" + case_param());
                        break;

                    default:
                        window.location.replace("/case" + case_param());
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