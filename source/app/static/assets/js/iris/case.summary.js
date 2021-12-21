var editor = ace.edit("editor_summary",
    {
    autoScrollEditorIntoView: true,
    minLines: 4
    });
editor.setTheme("ace/theme/tomorrow");
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


var session_id = null ;
var collaborator = null ;
var buffer_dumped = false ;
var last_applied_change = null ;
var just_cleared_buffer = null ;
var from_sync = null;

function Collaborator( session_id ) {
    this.collaboration_socket = io.connect() ;

    this.channel = "case-" + session_id;
    this.collaboration_socket.emit('join', { 'channel': this.channel });

    this.collaboration_socket.on( "change", function(data) {
        delta = JSON.parse( data.delta ) ;
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

var textarea = $('#case_summary');
editor.getSession().on("change", function () {
    textarea.val(editor.getSession().getValue());
    $('#last_saved').text('Changes not saved').addClass('badge-danger').removeClass('badge-success');
    target = document.getElementById('targetDiv'),
    converter = new showdown.Converter({
        tables: true,
        extensions: ['bootstrap-tables']
    }),
    html = converter.makeHtml(editor.getSession().getValue());

    target.innerHTML = html;
    
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
    } else {
        $('#ctrd_casesum').removeClass('col-md-6').addClass('col-md-12');
    }
}

/* sync_editor
* Save the editor state.
* Check if there are external changes first.
* Copy local changes if conflict
*/
function sync_editor(no_check) {

    $('#last_saved').text('Syncing..').addClass('badge-danger').removeClass('badge-success');
    $.ajax({
        url: '/case/summary/fetch' + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                if (no_check) {
                    // Set the content from remote server
                    from_sync = true;
                    editor.getSession().setValue(data.data.case_description);

                    // Set the CRC in page 
                    $('#fetched_crc').val(data.data.crc32);
                    $('#last_saved').text('Changes saved').removeClass('badge-danger').addClass('badge-success');
                    $('#content_last_sync').text("Last synced: " + new Date().toLocaleTimeString());
                }
                else {
                    // Check if content is different 
                    st = editor.getSession().getValue();
                    if (data.data.crc32 != $('#fetched_crc').val()) {
                        // Content has changed remotely 
                        // Check if we have changes locally 
                        local_crc = CRC32.str(st);
                        //if (local_crc == $('#fetched_crc').val()) {
                            // No local change, we can sync and update local CRC
                        editor.getSession().setValue(data.data.case_description);
                        $('#fetched_crc').val(data.data.crc32);
                        $('#last_saved').text('Changes saved').removeClass('badge-danger').addClass('badge-success');
                        $('#content_last_sync').text("Last synced: " + new Date().toLocaleTimeString());

//                        } else {
//                            // We have a conflict
//                            $('#last_saved').text('Conflict !').addClass('badge-danger').removeClass('badge-success');
//                            swal ( "Oh no !" ,
//                            "We have a conflict with the remote content.\nSomeone may just have changed the description at the same time.\nThe local content will be copied into clipboard and content will be updated with remote." ,
//                            "error"
//                            ).then((value) => {
//                                // Old fashion trick
//                                editor.selectAll();
//                                editor.focus();
//                                document.execCommand('copy');
//                                editor.getSession().setValue(data.data.desc);
//                                $('#fetched_crc').val(data.data.crc32);
//                                notify_success('Content updated with remote. Local changes copied to clipboard.');
//                                $('#content_last_sync').text("Last synced: " + new Date().toLocaleTimeString());
//                            });
//                        }
                    } else {
                        // Content did not change remotely
                        // Check local change 
                        local_crc = CRC32.str(st);
                        if (local_crc != $('#fetched_crc').val()) {

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
                                        $('#fetched_crc').val(local_crc);
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
        },
        error: function (error) {
            notify_error(error.message);
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

$(document).ready(function() {
    edit_case_summary();
    body_loaded();
    if (is_db_linked == 1) {
        sync_editor(true);
        setInterval(auto_remove_typing, 3000);
    }

    $('#generate_report_button').attr("href", '/report/generate/case/' + $("#select_report option:selected").val() + case_param());
    $("#select_report").on("change", function(){
        $('#generate_report_button').attr("href", '/report/generate/case/' + $("#select_report option:selected").val() + case_param());
    });

    $('#generate_report_act_button').attr("href", '/report/generate/activities/' + $("#select_report_act option:selected").val() + case_param());
    $("#select_report_act").on("change", function(){
        $('#generate_report_act_button').attr("href", '/report/generate/activities/' + $("#select_report_act option:selected").val() + case_param());
    });
});


