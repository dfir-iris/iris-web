var session_id = null ;
var collaborator = null ;
var buffer_dumped = false ;
var last_applied_change = null ;
var just_cleared_buffer = null ;
var from_sync = null;

var editor = ace.edit("editor_summary",
    {
    autoScrollEditorIntoView: true,
    minLines: 4
    });

var textarea = $('#case_summary');

function Collaborator( session_id ) {
    this.collaboration_socket = io.connect() ;

    this.channel = "case-" + session_id;
    this.collaboration_socket.emit('join', { 'channel': this.channel });

    this.collaboration_socket.on( "change", function(data) {
        delta = JSON.parse( data.delta ) ;
        console.log(delta);
        last_applied_change = delta ;
        $("#content_typing").text(data.last_change + " is typing..");
        editor.getSession().getDocument().applyDeltas( [delta] ) ;
    }.bind() ) ;

    this.collaboration_socket.on( "clear_buffer", function() {
        just_cleared_buffer = true ;
        console.log( "setting editor empty" ) ;
        editor.setValue( "" ) ;
    }.bind() ) ;

    this.collaboration_socket.on( "save", function(data) {
        $("#content_last_saved_by").text("Last saved by " + data.last_saved);
         sync_editor(true);
    }.bind() ) ;
}

Collaborator.prototype.change = function( delta ) {
    this.collaboration_socket.emit( "change", { 'delta': delta, 'channel': this.channel } ) ;
}

Collaborator.prototype.clear_buffer = function() {
    this.collaboration_socket.emit( "clear_buffer", { 'channel': this.channel } ) ;
}

Collaborator.prototype.save = function() {
    this.collaboration_socket.emit( "save", { 'channel': this.channel } ) ;
}

function body_loaded() {

    collaborator = new Collaborator( get_caseid() ) ;

    // registering change callback
    from_sync = true;
    editor.on( "change", function( e ) {
        // TODO, we could make things more efficient and not likely to conflict by keeping track of change IDs
        if( last_applied_change!=e && editor.curOp && editor.curOp.command.name) {
            collaborator.change( JSON.stringify(e) ) ;
        }
    }, false );

    editor.$blockScrolling = Infinity ;

    document.getElementsByTagName('textarea')[0].focus() ;
    last_applied_change = null ;
    just_cleared_buffer = false ;
}

function handle_ed_paste(event) {
    filename = null;
    const { items } = event.originalEvent.clipboardData;
    for (let i = 0; i < items.length; i += 1) {
      const item = items[i];

      if (item.kind === 'string') {
        item.getAsString(function (s){
            filename = $.trim(s.replace(/\t|\n|\r/g, '')).substring(0, 40);
        });
      }

      if (item.kind === 'file') {
        const blob = item.getAsFile();

        if (blob !== null) {
            const reader = new FileReader();
            reader.onload = (e) => {
                notify_success('The file is uploading in background. Don\'t leave the page');

                if (filename === null) {
                    filename = random_filename(25);
                }

                upload_interactive_data(e.target.result, filename, function(data){
                    url = data.data.file_url + case_param();
                    event.preventDefault();
                    editor.insertSnippet(`\n![${filename}](${url} =40%x40%)\n`);
                });

            };
            reader.readAsDataURL(blob);
        } else {
            notify_error('Unsupported direct paste of this item. Use datastore to upload.');
        }
      }
    }
}

var sh_ext = showdown.extension('bootstrap-tables', function () {
  return [{
    type: "output",
    filter: function (html, converter, options) {
      // parse the html string
      var liveHtml = $('<div></div>').html(html);
      $('table', liveHtml).each(function(){
      	var table = $(this);
        // table bootstrap classes
        table.addClass('table table-striped table-bordered table-hover table-sm')
        // make table responsive
        .wrap('<div class="class table-responsive"></div>');
      });
      return liveHtml.html();
    }
  }];
});

function report_template_selector() {
    $('#modal_select_report').modal({ show: true });
}

function act_report_template_selector() {
    $('#modal_select_report_act').modal({ show: true });
}

function edit_case_summary() {
    $('#container_editor_summary').toggle();
    if ($('#container_editor_summary').is(':visible')) {
        $('#ctrd_casesum').removeClass('col-md-12').addClass('col-md-6');
        $('#summary_edition_btn').show(100);
        $("#refreshbtn").html('Save');
    } else {
        $('#ctrd_casesum').removeClass('col-md-6').addClass('col-md-12');
        $('#summary_edition_btn').hide();
        $("#refreshbtn").html('Refresh');
    }
}

/* sync_editor
* Save the editor state.
* Check if there are external changes first.
* Copy local changes if conflict
*/
function sync_editor(no_check) {

    $('#last_saved').text('Syncing..').addClass('badge-danger').removeClass('badge-success');

    get_request_api('/case/summary/fetch')
    .done((data) => {
        if (data.status == 'success') {
            if (no_check) {
                // Set the content from remote server
                from_sync = true;
                editor.getSession().setValue(data.data.case_description);

                // Set the CRC in page
                $('#fetched_crc').val(data.data.crc32.toString());
                $('#last_saved').text('Changes saved').removeClass('badge-danger').addClass('badge-success');
                $('#content_last_sync').text("Last synced: " + new Date().toLocaleTimeString());
            }
            else {
                // Check if content is different
                st = editor.getSession().getValue();
                if (data.data.crc32 != $('#fetched_crc').val()) {
                    // Content has changed remotely
                    // Check if we have changes locally
                    local_crc = crc32(st).toString();
                    console.log('Content changed. Local CRC is ' + local_crc);
                    console.log('Saved CRC is ' + $('#fetched_crc').val());
                    console.log('Remote CRC is ' + data.data.crc32);
                    if (local_crc == $('#fetched_crc').val()) {
                        // No local change, we can sync and update local CRC
                        editor.getSession().setValue(data.data.case_description);
                        $('#fetched_crc').val(data.data.crc32);
                        $('#last_saved').text('Changes saved').removeClass('badge-danger').addClass('badge-success');
                        $('#content_last_sync').text("Last synced: " + new Date().toLocaleTimeString());
                    } else {
                        // We have a conflict
                        $('#last_saved').text('Conflict !').addClass('badge-danger').removeClass('badge-success');
                        swal ( "Oh no !" ,
                        "We have a conflict with the remote content.\nSomeone may just have changed the description at the same time.\nThe local content will be copied into clipboard and content will be updated with remote." ,
                        "error"
                        ).then((value) => {
                            // Old fashion trick
                            editor.selectAll();
                            editor.focus();
                            document.execCommand('copy');
                            editor.getSession().setValue(data.data.desc);
                            $('#fetched_crc').val(data.data.crc32);
                            notify_success('Content updated with remote. Local changes copied to clipboard.');
                            $('#content_last_sync').text("Last synced: " + new Date().toLocaleTimeString());
                        });
                    }
                } else {
                    // Content did not change remotely
                    // Check local change
                    local_crc = crc32(st).toString();
                    if (local_crc != $('#fetched_crc').val()) {
                        console.log('Local change. Old CRC is ' + local_crc);
                        console.log('New CRC is ' + $('#fetched_crc').val());
                        var data = Object();
                        data['case_description'] = st;
                        data['csrf_token'] = $('#csrf_token').val();
                        // Local change detected. Update to remote
                        $.ajax({
                            url: '/case/summary/update' + case_param(),
                            type: "POST",
                            dataType: "json",
                            contentType: "application/json;charset=UTF-8",
                            data: JSON.stringify(data),
                            success: function (data) {
                                if (data.status == 'success') {
                                    collaborator.save();
                                    $('#content_last_sync').text("Last synced: " + new Date().toLocaleTimeString());
                                    $('#fetched_crc').val(data.data);
                                    $('#last_saved').text('Changes saved').removeClass('badge-danger').addClass('badge-success');
                                } else {
                                    notify_error("Unable to save content to remote server");
                                    $('#last_saved').text('Error saving !').addClass('badge-danger').removeClass('badge-success');
                                }
                            },
                            error: function(error) {
                                notify_error(error.responseJSON.message);
                                ('#last_saved').text('Error saving !').addClass('badge-danger').removeClass('badge-success');
                            }
                        });
                    }
                    $('#content_last_sync').text("Last synced: " + new Date().toLocaleTimeString());
                    $('#last_saved').text('Changes saved').removeClass('badge-danger').addClass('badge-success');
                }
            }
        }
    });
}


is_typing = "";
function auto_remove_typing() {
    if ($("#content_typing").text() == is_typing) {
        $("#content_typing").text("");
    } else {
        is_typing = $("#content_typing").text();
    }
}

function case_pipeline_popup() {
    url = '/case/pipelines-modal' + case_param();
    $('#info_case_modal_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        $('#modal_case_detail').modal({ show: true });
        $("#update_pipeline_selector").selectpicker({
            liveSearch: true,
            style: "btn-outline-white"
            })
        $('#update_pipeline_selector').selectpicker("refresh");
        $(".control-update-pipeline-args ").hide();
        $('.control-update-pipeline-'+ $('#update_pipeline_selector').val() ).show();
        $('#update_pipeline_selector').on('change', function(e){
          $(".control-update-pipeline-args ").hide();
          $('.control-update-pipeline-'+this.value).show();
        });
        $('[data-toggle="popover"]').popover();
    });
}

function case_detail(case_id) {
    url = '/case/details/' + case_id + case_param();
    $('#info_case_modal_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        $('#modal_case_detail').modal({ show: true });
    });
}

function manage_case(case_id) {
   window.location = '/manage/cases?cid='+ case_id +'#view';
}


$(document).ready(function() {

    if ($("#editor_summary").attr("data-theme") != "dark") {
        editor.setTheme("ace/theme/tomorrow");
    } else {
        editor.setTheme("ace/theme/tomorrow_night");
    }
    editor.session.setMode("ace/mode/markdown");
    editor.renderer.setShowGutter(true);
    editor.setOption("showLineNumbers", true);
    editor.setOption("showPrintMargin", false);
    editor.setOption("displayIndentGuides", true);
    editor.setOption("indentedSoftWrap", false);
    editor.session.setUseWrapMode(true);
    editor.setOption("maxLines", "Infinity")
    editor.renderer.setScrollMargin(8, 5)
    editor.setOption("enableBasicAutocompletion", true);
    editor.commands.addCommand({
        name: 'save',
        bindKey: {win: "Ctrl-S", "mac": "Cmd-S"},
        exec: function(editor) {
            sync_editor(false);
        }
    })
    editor.commands.addCommand({
        name: 'bold',
        bindKey: {win: "Ctrl-B", "mac": "Cmd-B"},
        exec: function(editor) {
            editor.insertSnippet('**${1:$SELECTION}**');
        }
    });
    editor.commands.addCommand({
        name: 'italic',
        bindKey: {win: "Ctrl-I", "mac": "Cmd-I"},
        exec: function(editor) {
            editor.insertSnippet('*${1:$SELECTION}*');
        }
    });
    editor.commands.addCommand({
        name: 'head_1',
        bindKey: {win: "Ctrl-Shift-1", "mac": "Cmd-Shift-1"},
        exec: function(editor) {
            editor.insertSnippet('# ${1:$SELECTION}');
        }
    });
    editor.commands.addCommand({
        name: 'head_2',
        bindKey: {win: "Ctrl-Shift-2", "mac": "Cmd-Shift-2"},
        exec: function(editor) {
            editor.insertSnippet('## ${1:$SELECTION}');
        }
    });
    editor.commands.addCommand({
        name: 'head_3',
        bindKey: {win: "Ctrl-Shift-3", "mac": "Cmd-Shift-3"},
        exec: function(editor) {
            editor.insertSnippet('### ${1:$SELECTION}');
        }
    });
    editor.commands.addCommand({
        name: 'head_4',
        bindKey: {win: "Ctrl-Shift-4", "mac": "Cmd-Shift-4"},
        exec: function(editor) {
            editor.insertSnippet('#### ${1:$SELECTION}');
        }
    });
    $('#editor_summary').on('paste', (event) => {
        event.preventDefault();
        handle_ed_paste(event);
    });

    var timer;
    var timeout = 10000;
    $('#editor_summary').keyup(function(){
        if(timer) {
             clearTimeout(timer);
        }
        timer = setTimeout(sync_editor, timeout);
    });


    var textarea = $('#case_summary');
    editor.getSession().on("change", function () {
        textarea.val(editor.getSession().getValue());
        $('#last_saved').text('Changes not saved').addClass('badge-danger').removeClass('badge-success');
        target = document.getElementById('targetDiv'),
        converter = new showdown.Converter({
            tables: true,
            extensions: ['bootstrap-tables'],
            parseImgDimensions: true
        }),
        html = converter.makeHtml(editor.getSession().getValue());

        target.innerHTML = filterXSS(html);

    });

    edit_case_summary();
    body_loaded();
    if (is_db_linked == 1) {
        sync_editor(true);
        setInterval(auto_remove_typing, 2000);
    }

    if ($("#select_report_act option:selected").val() !== undefined) {
        $('#generate_report_button').attr("href", '/case/report/generate-investigation/' + $("#select_report option:selected").val() + case_param());
        $("#select_report").on("change", function(){
            $('#generate_report_button').attr("href", '/case/report/generate-investigation/' + $("#select_report option:selected").val() + case_param());
        });

        $('#generate_report_button_safe').attr("href", '/case/report/generate-investigation/' + $("#select_report option:selected").val() + case_param() + "&safe-mode=true");
        $("#select_report").on("change", function(){
            $('#generate_report_button_safe').attr("href", '/case/report/generate-investigation/' + $("#select_report option:selected").val() + case_param() + "&safe-mode=true");
        });
    } else {
         $('#generate_report_button').attr("href", '#');
         $('#generate_report_button_safe').attr("href", '#');
    }

    if ($("#select_report_act option:selected").val() !== undefined) {
        $('#generate_report_act_button').attr("href", '/case/report/generate-activities/' + $("#select_report_act option:selected").val() + case_param());
        $("#select_report_act").on("change", function(){
            $('#generate_report_act_button').attr("href", '/case/report/generate-activities/' + $("#select_report_act option:selected").val() + case_param());
        });

        $('#generate_report_act_button_safe').attr("href", '/case/report/generate-activities/' + $("#select_report_act option:selected").val() + case_param() + "&safe-mode=true");
        $("#select_report_act").on("change", function(){
            $('#generate_report_act_button_safe').attr("href", '/case/report/generate-activities/' + $("#select_report_act option:selected").val() + case_param() + "&safe-mode=true");
        });

    } else {
        $('#generate_report_act_button').attr("href", '#');
        $('#generate_report_act_button_safe').attr("href", '#');
    }


});


