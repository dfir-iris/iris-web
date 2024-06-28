/* Defines the kanban board */
let note_editor;
let session_id = null ;
let collaborator = null ;
let collaborator_socket = null ;
let last_applied_change = null ;
let just_cleared_buffer = null ;
let is_typing = "";
let ppl_viewing = new Map();
let timer_socket = 0;
let note_id = null;
let last_ping = 0;
let cid = null;
let previousNoteTitle = null;
let timer = null;
let timeout = 5000;


const preventFormDefaultBehaviourOnSubmit = (event) => {
    event.preventDefault();
    return false;
};


function Collaborator( session_id, n_id ) {
    this.collaboration_socket = collaborator_socket;

    this.channel = "case-" + session_id + "-notes";

    this.collaboration_socket.off("change-note");
    this.collaboration_socket.off("clear_buffer-note");
    this.collaboration_socket.off("save-note");
    this.collaboration_socket.off("leave-note");
    this.collaboration_socket.off("join-note");
    this.collaboration_socket.off("pong-note");
    this.collaboration_socket.off("disconnect");


    this.collaboration_socket.on("change-note", function (data) {
        // Set as int to avoid type mismatch
        if (parseInt(data.note_id) !== parseInt(note_id)) return;

        let delta = JSON.parse(data.delta);
        last_applied_change = delta;
        $("#content_typing").text(data.last_change + " is typing..");
        if (delta !== null && delta !== undefined) {
            note_editor.session.getDocument().applyDeltas([delta]);
        }
    }.bind());

    this.collaboration_socket.on("clear_buffer-note", function () {
        if (parseInt(data.note_id) !== parseInt(note_id)) return;
        just_cleared_buffer = true;
        note_editor.setValue("");
    }.bind());

    this.collaboration_socket.on("save-note", function (data) {
        if (parseInt(data.note_id) !== parseInt(note_id)) return;
        sync_note(note_id)
            .then(function () {
                $("#content_last_saved_by").text("Last saved by " + data.last_saved);
                $('#btn_save_note').text("Saved").addClass('btn-success').removeClass('btn-danger').removeClass('btn-warning');
                $('#last_saved').removeClass('btn-danger').addClass('btn-success');
                $('#last_saved > i').attr('class', "fa-solid fa-file-circle-check");
            });

    }.bind());

    this.collaboration_socket.on('leave-note', function (data) {
        ppl_viewing.delete(data.user);
        refresh_ppl_list(session_id, note_id);
    });

    this.collaboration_socket.on('join-note', function (data) {
        if (parseInt(data.note_id) !== parseInt(note_id)) return;
        if ((data.user in ppl_viewing)) return;
        ppl_viewing.set(filterXSS(data.user), 1);
        refresh_ppl_list(session_id, note_id);
        collaborator.collaboration_socket.emit('ping-note', {'channel': collaborator.channel, 'note_id': note_id});
    });

    this.collaboration_socket.on('ping-note', function (data) {
        if (data.note_id !== note_id) return;
        collaborator.collaboration_socket.emit('pong-note', {'channel': collaborator.channel, 'note_id': note_id});
    });

    this.collaboration_socket.on('disconnect', function (data) {
        ppl_viewing.delete(data.user);
        refresh_ppl_list(session_id, note_id);
    });

}

Collaborator.prototype.change = function( delta, note_id ) {
    this.collaboration_socket.emit( "change-note", { 'delta': delta, 'channel': this.channel, 'note_id': note_id } ) ;
}

Collaborator.prototype.clear_buffer = function( note_id ) {
    this.collaboration_socket.emit( "clear_buffer-note", { 'channel': this.channel, 'note_id': note_id } ) ;
}

Collaborator.prototype.save = function( note_id ) {
    this.collaboration_socket.emit( "save-note", { 'channel': this.channel, 'note_id': note_id } ) ;
}

Collaborator.prototype.close = function( note_id ) {
    this.collaboration_socket.emit( "leave-note", { 'channel': this.channel, 'note_id': note_id } ) ;
}

function auto_remove_typing() {
    if ($("#content_typing").text() == is_typing) {
        $("#content_typing").text("");
    } else {
        is_typing = $("#content_typing").text();
    }
}

/* Generates a global sequence id for subnotes */
let current_id = 0;

/* Generates a global sequence id for groups */
var current_gid = 0;

async function get_remote_note(note_id) {
    return get_request_api("/case/notes/" + note_id);
}

async function sync_note(node_id) {
    // Get the remote note
    let remote_note = await get_remote_note(node_id);
    if (remote_note.status !== 'success') {
        return;
    }

    // Get the local note
    let local_note = note_editor.getValue();

    // If the local note is empty, set it to the remote note
    if (local_note === '') {
        note_editor.setValue(remote_note.data.note_content, -1);
        return;
    }

    // If the local note is not empty, check if it is different from the remote note
    if (local_note !== remote_note.data.note_content) {
        swal({
            title: 'Note conflict',
            text: 'The note has been saved by someone else. Do you want to overwrite your changes?',
            icon: 'warning',
            buttons: {
                cancel: {
                    text: 'Cancel',
                    value: null,
                    visible: true,
                },
                confirm: {
                    text: 'Overwrite',
                    value: true,
                }
            },
            dangerMode: true,
            closeOnEsc: false,
            allowOutsideClick: false,
            allowEnterKey: false
        })
            .then((overwrite) => {
                if (overwrite) {
                    // Overwrite the local note with the remote note
                    note_editor.setValue(remote_note.data.note_content, -1);
                }
            });
    }

    return;
}


function delete_note(_item, cid) {
    if (_item === undefined || _item === null) {
        _item = $('#currentNoteIDLabel').data('note_id')
    }

    do_deletion_prompt("You are about to delete note #" + _item)
    .then((doDelete) => {
        if (doDelete) {
            post_request_api('/case/notes/delete/' + _item, null, null, cid)
            .done((data) => {
               if (notify_auto_api(data)) {
                   load_directories()
                       .then((data) =>
                       {
                           let shared_id = getSharedLink();
                            if (shared_id) {
                                note_detail(shared_id).then((data) => {
                                    if (!data) {
                                        setSharedLink(null);
                                        toggleNoteEditor(false);
                                    }
                                });
                            }
                       }
                   )
               }
            })
        }
    });
}

function proxy_comment_element() {
    let note_id = $('#currentNoteIDLabel').data('note_id');

    return comment_element(note_id, 'notes');
}

function proxy_copy_object_link() {
    let note_id = $('#currentNoteIDLabel').data('note_id');

    return copy_object_link(note_id);
}

function proxy_copy_object_link_md() {
    let note_id = $('#currentNoteIDLabel').data('note_id');

    return copy_object_link_md('note', note_id);
}

function toggleNoteEditor(show_editor) {
    if (show_editor) {
        $('#currentNoteContent').show();
        $('#emptyNoteDisplay').hide();
    } else {
        $('#currentNoteContent').hide();
        $('#emptyNoteDisplay').show();
    }
}

/* Edit one note */
function edit_note(event) {

    var nval = $(event).find('iris_note').attr('id');
    collaborator = null;
    note_detail(nval);

}


function setSharedLink(id) {
    // Set the shared ID in the URL
    let url = new URL(window.location.href);
    if (id !== undefined && id !== null) {
        url.searchParams.set('shared', id);
    } else {
        url.searchParams.delete('shared');
    }
    window.history.replaceState({}, '', url);
}

async function load_note_revisions(_item) {

    if (_item === undefined || _item === null) {
        _item = $('#currentNoteIDLabel').data('note_id')
    }

    get_request_api('/case/notes/' + _item + '/revisions/list')
    .done((data) => {
        if (notify_auto_api(data, true)) {
            let revisions = data.data;
            let revisionList = $('#revisionList');
            revisionList.empty();

            revisions.forEach(function(revision) {
                let listItem = $('<li></li>').addClass('list-group-item');
                let link = $('<a class="btn btn-sm btn-outline-dark float-right ml-1" href="#"><i class="fa-solid fa-clock-rotate-left" style="cursor: pointer;" title="Revert"></i> Revert</a>');
                let link_preview = $('<a class="btn btn-sm btn-outline-dark float-right ml-1" href="#"><i class="fa-solid fa-eye" style="cursor: pointer;" title="Preview"></i> Preview</a>');
                let link_delete = $('<a class="btn btn-sm btn-outline-danger float-right ml-1" href="#"><i class="fa-solid fa-trash" style="cursor: pointer;" title="Delete"></i></a>');
                let user = $('<span></span>').text(`#${revision.revision_number} by ${revision.user_name} on ${formatTime(revision.revision_timestamp)}`);
                listItem.append(user);
                listItem.append(link_delete);
                listItem.append(link);
                listItem.append(link_preview);

                revisionList.append(listItem);

                link.on('click', function(e) {
                    e.preventDefault();
                    note_revision_revert(_item, revision.revision_number);
                });

                link_delete.on('click', function(e) {
                    e.preventDefault();
                    note_revision_delete(_item, revision.revision_number);
                });

                link_preview.on('click', function(e) {
                    e.preventDefault();
                    get_request_api('/case/notes/' + _item + '/revisions/' + revision.revision_number)
                    .done((data) => {
                        if (notify_auto_api(data, true)) {
                            let revision = data.data;
                            $('#previewRevisionID').text(revision.revision_number);
                            $('#notePreviewModalTitle').text(`#${revision.revision_number} - ${revision.note_title}`);
                            let note_prev = get_new_ace_editor('notePreviewModalContent', 'note_content', 'targetDiv');
                            note_prev.setValue(revision.note_content, -1);
                            note_prev.setReadOnly(true);
                            $('#notePreviewModal').modal('show');
                        }
                    });
                });

                $('#noteModificationHistoryModal').modal('show');

            });
        }
    });
}

function note_revision_revert(_item, _rev) {
    if (_item === undefined || _item === null) {
        _item = $('#currentNoteIDLabel').data('note_id')
    }
    let close_modal = false;
    if (_rev === undefined || _rev === null) {
        _rev = $('#previewRevisionID').text();
        close_modal = true;
    }

    get_request_api('/case/notes/' + _item + '/revisions/' + _rev)
    .done((data) => {
        if (notify_auto_api(data, true)) {
            let revision = data.data;
            $('#currentNoteTitle').text(revision.note_title);
            note_editor.setValue(revision.note_content, -1);
            if (close_modal) {
                $('#notePreviewModal').modal('hide');
            }
            $('#noteModificationHistoryModal').modal('hide');
            notify_success('Note reverted to revision #' + _rev + '. Save to apply changes.');
        }
    });
}

function note_revision_delete(_item, _rev) {
    if (_item === undefined || _item === null) {
        _item = $('#currentNoteIDLabel').data('note_id')
    }

    let close_modal = false;
    if (_rev === undefined || _rev === null) {
        _rev = $('#previewRevisionID').text();
        close_modal = true;
    }

    do_deletion_prompt("You are about to delete revision #" + _rev)
    .then((doDelete) => {
        if (doDelete) {
            post_request_api('/case/notes/' + _item + '/revisions/' + _rev + '/delete')
            .done((data) => {
                if (notify_auto_api(data, false)) {
                    load_note_revisions(_item);
                }

                if (close_modal) {
                    $('#notePreviewModal').modal('hide');
                }

            });
        }
    });
}

/* Fetch the edit modal with content from server */
async function note_detail(id) {

    get_request_api('/case/notes/' + id)
    .done((data) => {
        if (notify_auto_api(data, true, true)) {
            let timer;
            let timeout = 10000;
            $('#form_note').keyup(function(){
                if(timer) {
                     clearTimeout(timer);
                }
                if (ppl_viewing.size <= 1) {
                    timer = setTimeout(save_note, timeout);
                }
            });

            note_id = id;

            if (collaborator !== null) {
                collaborator.close(note_id);
            }

            collaborator = new Collaborator( get_caseid() );

            // Destroy the note editor if it exists
            if (note_editor !== undefined && note_editor !== null) {
                note_editor.destroy();
                note_editor = null;
            }

            note_editor = get_new_ace_editor('editor_detail', 'note_content', 'targetDiv', function () {
                $('#last_saved').addClass('btn-danger').removeClass('btn-success');
                $('#last_saved > i').attr('class', "fa-solid fa-file-circle-exclamation");
                $('#btn_save_note').text("Save").removeClass('btn-success').addClass('btn-warning').removeClass('btn-danger');
            }, save_note);

            note_editor.focus();

            note_editor.setValue(data.data.note_content, -1);
            $('#currentNoteTitle').text(data.data.note_title);
            previousNoteTitle = data.data.note_title;
            $('#currentNoteIDLabel').text(`#${data.data.note_id} - ${data.data.note_uuid}`)
                .data('note_id', data.data.note_id);

            note_editor.on( "change", function( e ) {
                if( last_applied_change != e && note_editor.curOp && note_editor.curOp.command.name) {
                    console.log('Change detected - signaling teammates');
                    collaborator.change( JSON.stringify(e), note_id ) ;
                }
                }, false
            );
            last_applied_change = null ;
            just_cleared_buffer = false ;

            load_menu_mod_options_modal(id, 'note', $("#note_quick_actions"));

            collaborator_socket.emit('ping-note', { 'channel': 'case-' + get_caseid() + '-notes', 'note_id': note_id });

            toggleNoteEditor(true);

            $('.note').removeClass('note-highlight');
            $('#note-' + id).addClass('note-highlight');

            $('#object_comments_number').text(data.data.comments.length);
            $('#content_last_saved_by').text('');
            $('#content_typing').text('');
            $('#last_saved').removeClass('btn-danger').addClass('btn-success');
            $('#last_saved > i').attr('class', "fa-solid fa-file-circle-check");

            let ed_details = $('#editor_detail');
            ed_details.keyup(function(){
                if(timer) {
                     clearTimeout(timer);
                }
                timer = setTimeout(save_note, timeout);
            });
            ed_details.off('paste');
            ed_details.on('paste', (event) => {
                event.preventDefault();
                handle_ed_paste(event);
            });

            setSharedLink(id);

            return true;
        } else {
            setSharedLink();
            return false;
        }

    });
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
                    note_editor.insertSnippet(`\n![${filename}](${url} =100%x40%)\n`);
                });
            };
			reader.readAsDataURL(blob);
        } else {
            notify_error('Unsupported direct paste of this item. Use datastore to upload.');
        }
      }
    }
}


function refresh_ppl_list() {
    $('#ppl_list_viewing').empty();
    for (let [key, value] of ppl_viewing) {
        $('#ppl_list_viewing').append(get_avatar_initials(key, false, undefined, true));
    }
}

/* Delete a group of the dashboard */
function search_notes() {
    var data = Object();
    data['search_term'] = $("#search_note_input").val();
    data['csrf_token'] = $("#csrf_token").val();

    post_request_api('/case/notes/search', JSON.stringify(data))
    .done((data) => {
        if (data.status == 'success') {
            $('#notes_search_list').empty();
            for (e in data.data) {
                let lit_tag = $('<li>');
                lit_tag.addClass('list-group-item list-group-item-action note');
                lit_tag.attr('id', 'note-' + data.data[e]['note_id']);
                lit_tag.attr('onclick', 'note_detail(' + data.data[e]['note_id'] + ');');
                lit_tag.text(data.data[e]['note_title']);
                $('#notes_search_list').append(lit_tag);

            }
            $('#notes_search_list').show();

        } else {
            if (data.message != "No data to load for dashboard") {
                swal("Oh no !", data.message, "error");
            }
        }
    })
}

function toggle_max_editor() {
    $('#ctrd_notesum').toggle();
    if ($('#ctrd_notesum').is(':visible')) {
        $('#btn_max_editor').html('<i class="fa-solid fa-maximize"></i>');
        $('#container_note_content').removeClass('col-md-12 col-lg-12').addClass('col-md-12 col-lg-6');
    } else {
        $('#btn_max_editor').html('<i class="fa-solid fa-minimize"></i>');
        $('#container_note_content').removeClass('col-md-12 col-lg-6').addClass('col-md-12 col-lg-12');
    }
}

/* Save a note into db */
function save_note() {
    clear_api_error();
    let n_id = $('#currentNoteIDLabel').data('note_id')


    let data_sent = Object();
    let currentNoteTitle = $('#currentNoteTitle').text() ? $('#currentNoteTitle').text() : $('#currentNoteTitleInput').val();
    data_sent['note_title'] = currentNoteTitle;
    data_sent['csrf_token'] = $('#csrf_token').val();
    data_sent['note_content'] = $('#note_content').val();
    let ret = get_custom_attributes_fields();
    let has_error = ret[0].length > 0;
    let attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;

    post_request_api('/case/notes/update/'+ n_id, JSON.stringify(data_sent), false, undefined, cid, function() {
        $('#btn_save_note').text("Error saving!").removeClass('btn-success').addClass('btn-danger').removeClass('btn-danger');
        $('#last_saved > i').attr('class', "fa-solid fa-file-circle-xmark");
        $('#last_saved').addClass('btn-danger').removeClass('btn-success');
    })
    .done((data) => {
        if (notify_auto_api(data, true)) {
            $('#btn_save_note').text("Saved").addClass('btn-success').removeClass('btn-danger').removeClass('btn-warning');
            $('#last_saved').removeClass('btn-danger').addClass('btn-success');
            $("#content_last_saved_by").text('Last saved by you');
            $('#last_saved > i').attr('class', "fa-solid fa-file-circle-check");

            collaborator.save(n_id);

            if (previousNoteTitle !== currentNoteTitle) {
                load_directories().then(function() {
                    $('.note').removeClass('note-highlight');
                    $('#note-' + n_id).addClass('note-highlight');
                });
                previousNoteTitle = currentNoteTitle;
            }
        }
    });
}

/* Span for note edition */
function edit_innote() {
    $('#container_note_content').toggle();
    if ($('#container_note_content').is(':visible')) {
        $('#notes_edition_btn').show(100);
        $('#ctrd_notesum').removeClass('col-md-11 col-lg-11 ml-4').addClass('col-md-6 col-lg-6');
    } else {
        $('#notes_edition_btn').hide(100);
        $('#ctrd_notesum').removeClass('col-md-6 col-lg-6').addClass('col-md-11 col-lg-11 ml-4');
    }
}

async function load_directories() {
    return get_request_api('/case/notes/directories/filter')
        .done((data) => {
            if (notify_auto_api(data, true)) {
                data = data.data;
                let directoriesListing = $('#directoriesListing');
                directoriesListing.empty();

                let directoryMap = new Map();
                data.forEach(function(directory) {
                    directoryMap.set(directory.id, directory);
                });

                let subdirectoryIds = new Set();
                data.forEach(function(directory) {
                    directory.subdirectories.forEach(function(subdirectory) {
                        subdirectoryIds.add(subdirectory.id);
                    });
                });

                let directories = data.filter(function(directory) {
                    return !subdirectoryIds.has(directory.id);
                });

                directories.forEach(function(directory) {
                    directoriesListing.append(createDirectoryListItem(directory, directoryMap));
                });
            }
        });
}

function download_note() {
    // Use directly the content of the note editor
    let content = note_editor.getValue();
    let filename = $('#currentNoteTitle').text() + '.md';
    let blob = new Blob([content], {type: 'text/plain'});
    let url = window.URL.createObjectURL(blob);

    // Create a link to the file and click it to download it
    let link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
}

function add_note(directory_id) {
    let data = Object();
    data['directory_id'] = directory_id;
    data['note_title'] = 'New note';
    data['note_content'] = '';
    data['csrf_token'] = $('#csrf_token').val();

    post_request_api('/case/notes/add', JSON.stringify(data))
    .done((data) => {
        if (notify_auto_api(data, true)) {
            note_detail(data.data.note_id);
            load_directories().then(function() {
                $('.note').removeClass('note-highlight');
                $('#note-' + data.data.note_id).addClass('note-highlight');
            });
        }
    });
}

function add_folder(directory_id) {
    let data = Object();
    data['parent_id'] = directory_id;
    data['name'] = 'New folder';
    data['csrf_token'] = $('#csrf_token').val();

    post_request_api('/case/notes/directories/add', JSON.stringify(data))
    .done((data) => {
        if (notify_auto_api(data, true)) {
            rename_folder(data.data.id);
        }
    });
}

function refresh_folders() {
    load_directories().then(function() {
        notify_success('Tree  refreshed');
        let note_id = $('#currentNoteIDLabel').data('note_id');
        $('.note').removeClass('note-highlight');
        $('#note-' + note_id).addClass('note-highlight');
    });
}

function toggleDirectories() {
    // Select all directory elements
    let directories = $('.directory-container');

    // Toggle the visibility of the directories
    directories.toggle();

}

function rename_folder_api(directory_id, newName) {
    let data = Object();
    data['name'] = newName;
    data['csrf_token'] = $('#csrf_token').val();

    post_request_api(`/case/notes/directories/update/${directory_id}`,
        JSON.stringify(data))
    .done((data) => {
        if (notify_auto_api(data)) {
            load_directories();
        }
    });
}

function delete_folder_api(directory_id) {
    let data = Object();
    data['csrf_token'] = $('#csrf_token').val();

    post_request_api(`/case/notes/directories/delete/${directory_id}`,
        JSON.stringify(data))
    .done((data) => {
        if (notify_auto_api(data)) {
            load_directories();
        }
    });
}

function move_note_api(note_id, new_directory_id) {
    let data = Object();
    data['csrf_token'] = $('#csrf_token').val();
    data['directory_id'] = new_directory_id;

    return post_request_api(`/case/notes/update/${note_id}`,
        JSON.stringify(data));
}

function move_item(item_id, item_type) {
    // Create a modal with a list of directories to move the folder to
    let modal = $('#moveFolderModal');

    let directoriesListing = $('<ul></ul>');
    $('#dirListingMove').empty().append(directoriesListing);

    let directoryMap = new Map();
    $('#directoriesListing').find('li').filter('.directory').each(function() {
        let directory = $(this).data('directory');
        directoryMap.set(directory.id, directory);
    });

    let subdirectoryIds = new Set();

    function addSubdirectoryIds(directory) {
        directory.subdirectories.forEach(function(subdirectory) {
            subdirectoryIds.add(subdirectory.id);
            let subdirectoryData = directoryMap.get(subdirectory.id);
            if (subdirectoryData) {
                addSubdirectoryIds(subdirectoryData);
            }
        });
    }

    directoryMap.forEach(function(directory) {
        addSubdirectoryIds(directory);
    });

    let directories = Array.from(directoryMap.values()).filter(function(directory) {
        return item_type === 'folder' ? (item_id !== directory.id) : true;
    });

    let listItem = $('<li></li>');
    let link = $('<a></a>').attr('href', '#').text('Root');
    listItem.append(link);

    link.on('click', function(e) {
        e.preventDefault();
        if (item_type === 'note') {
            move_note_api(item_id, null).then(function() {
                modal.modal('hide');
            });
        }
        else if (item_type === 'folder') {
            move_folder_api(item_id, null).then(function () {
                modal.modal('hide');
            });
        }
    });

    directoriesListing.append(listItem);

    directories.forEach(function(directory) {
        let listItem = $('<li></li>');
        let link = $('<a></a>').attr('href', '#');
        link.append($('<i></i>').addClass('fa-regular fa-folder mr-2'));  // Add a folder icon
        link.append(' ' + directory.name);
        listItem.append(link);

        link.on('click', function(e) {
            e.preventDefault();
            if (item_type === 'note') {
                move_note_api(item_id, directory.id).then(function() {
                    // reload the directories
                    load_directories()
                    .then(function() {
                        note_detail(item_id);
                        modal.modal('hide');
                    });
                });
            }
            else if (item_type === 'folder') {
                move_folder_api(item_id, directory.id).then(function () {
                    load_directories()
                    .then(function() {
                        modal.modal('hide');
                    });
                });
            }
        });

        directoriesListing.append(listItem);
    });

    modal.modal('show');
}

async function move_folder_api(directory_id, new_parent_id) {
    let data = Object();
    data['csrf_token'] = $('#csrf_token').val();
    data['parent_id'] = new_parent_id;

    return post_request_api(`/case/notes/directories/update/${directory_id}`,
        JSON.stringify(data))
    .done((data) => {
        if (notify_auto_api(data)) {
            load_directories();
        }
    });
}

function delete_folder(directory_id) {
    swal({
        title: 'Delete folder',
        text: 'Are you sure you want to delete this folder? All subfolders and notes will be deleted as well.',
        icon: 'warning',
        buttons: {
            cancel: {
                text: 'Cancel',
                value: null,
                visible: true,
            },
            confirm: {
                text: 'Delete',
                value: true,
            }
        },
        dangerMode: true,
        closeOnEsc: false,
        allowOutsideClick: false,
        allowEnterKey: false
    })
        .then((willDelete) => {
            if (willDelete) {
                delete_folder_api(directory_id);
            }
        });
}

function rename_folder(directory_id, new_directory=false) {

    // Prompt the user for a new name
    swal({
        title: new_directory?  'Rename directory': "Name the new folder",
        text: 'Enter a new name for the folder',
        content: 'input',
        buttons: {
            cancel: {
                text: 'Cancel',
                value: null,
                visible: true,
            },
            confirm: {
                text: new_directory ? 'Ok' : 'Rename',
                value: true,
            }
        },
        dangerMode: true,
        closeOnEsc: false,
        allowOutsideClick: false,
        allowEnterKey: false
    })
        .then((newName) => {
            if (newName) {
                rename_folder_api(directory_id, newName);
            }
        });
}

function fetchNotes(searchInput) {
    // Send a GET request to the server with the search input as a parameter
    get_raw_request_api('/case/notes/search?search_input=' + encodeURIComponent(searchInput) + '&cid=' + get_caseid())
        .done(data => {
            if (notify_auto_api(data, true)) {
                $('.directory-container').find('li').hide();
                $('.directory').hide();
                $('.note').hide();

                data.data.forEach(note => {
                    // Show the note
                    $('#note-' + note.note_id).show();

                    // Show all ancestor directories of the note
                    let parentDirectory = $('#directory-' + note.directory_id);
                    while (parentDirectory.length > 0) {
                        parentDirectory.show();
                        parentDirectory = parentDirectory.parents('.directory').first();
                    }
                });
            }
        });
}

function getNotesInfo(directory, directoryMap, currentNoteID) {
    let totalNotes = directory.notes.length;
    let hasMoreThanFiveNotes = directory.notes.length > 5;
    let dirContainsCurrentNote = directory.notes.some(note => note.id == currentNoteID);

    for (let i = 0; i < directory.subdirectories.length; i++) {
        let subdirectoryId = directory.subdirectories[i].id;
        let subdirectory = directoryMap.get(subdirectoryId);
        if (subdirectory) {
            let subdirectoryInfo = getNotesInfo(subdirectory, directoryMap, currentNoteID);
            totalNotes += subdirectoryInfo.totalNotes;
            hasMoreThanFiveNotes = hasMoreThanFiveNotes || subdirectoryInfo.hasMoreThanFiveNotes;
            dirContainsCurrentNote = dirContainsCurrentNote || subdirectoryInfo.dirContainsCurrentNote;
        }
    }

    return { totalNotes, hasMoreThanFiveNotes, dirContainsCurrentNote };
}



function createDirectoryListItem(directory, directoryMap) {
    // Create a list item for the directory
    var listItem = $('<li></li>').attr('id', 'directory-' + directory.id).addClass('directory');
    listItem.data('directory', directory);
    var link = $('<a></a>').attr('href', '#');
    var icon = $('<i></i>').addClass('fa-regular fa-folder');  // Create an icon for the directory
    link.append(icon);
    link.append($('<span>').text(directory.name));
    listItem.append(link);

    let currentNoteID = getSharedLink();

    var container = $('<div></div>').addClass('directory-container');
    listItem.append(container);

    let notesInfo = getNotesInfo(directory, directoryMap, currentNoteID);
    icon.append($('<span></span>').addClass('notes-number').text(notesInfo.totalNotes));
    if (!notesInfo.hasMoreThanFiveNotes || notesInfo.dirContainsCurrentNote) {
        icon.removeClass('fa-folder').addClass('fa-folder-open');
    } else {
        container.hide();
    }

    link.on('click', function(e) {
        e.preventDefault();
        container.slideToggle();
        icon.toggleClass('fa-folder fa-folder-open');
    });

    link.on('contextmenu', function(e) {
        e.preventDefault();

        let menu = $('<div></div>').addClass('dropdown-menu show').css({
            position: 'absolute',
            left: e.pageX,
            top: e.pageY
        });

        menu.append($('<a></a>').addClass('dropdown-item').attr('href', '#').text('Add note').on('click', function(e) {
            e.preventDefault();
            add_note(directory.id);
        }));
        menu.append($('<a></a>').addClass('dropdown-item').attr('href', '#').text('Add directory').on('click', function(e) {
            e.preventDefault();
            add_folder(directory.id);
        }));

        menu.append($('<div></div>').addClass('dropdown-divider'));
        menu.append($('<a></a>').addClass('dropdown-item').attr('href', '#').text('Rename').on('click', function(e) {
            e.preventDefault();
            rename_folder(directory.id);
        }));
        menu.append($('<a></a>').addClass('dropdown-item').attr('href', '#').text('Move').on('click', function(e) {
            e.preventDefault();
            move_item(directory.id, 'folder');
        }));

        menu.append($('<div></div>').addClass('dropdown-divider'));
        menu.append($('<a></a>').addClass('dropdown-item text-danger').attr('href', '#').text('Delete').on('click', function(e) {
            e.preventDefault();
            delete_folder(directory.id);
        }));

        $('body').append(menu).on('click', function() {
            menu.remove();
        });
    });

    // If the directory has subdirectories, create a list item for each subdirectory
    if (directory.subdirectories && directory.subdirectories.length > 0) {
        var subdirectoriesList = $('<ul></ul>').addClass('nav');
        directory.subdirectories.forEach(function(subdirectory) {
            // Look up the subdirectory in the directoryMap
            var subdirectoryData = directoryMap.get(subdirectory.id);
            if (subdirectoryData) {
                subdirectoriesList.append(createDirectoryListItem(subdirectoryData, directoryMap));
            }
        });
        container.append(subdirectoriesList);
    }

    // If the directory has notes, create a list item for each note
    if (directory.notes && directory.notes.length > 0) {
        var notesList = $('<ul></ul>').addClass('nav');
        directory.notes.forEach(function(note) {
            var noteListItem = $('<li></li>').attr('id', 'note-' + note.id).addClass('note');
            var noteLink = $('<a></a>').attr('href', '#');

            noteLink.append($('<i></i>').addClass('fa-regular fa-file'));
            noteLink.append($('<span>').text(note.title));

            // Add a click event listener to the note link that calls note_detail with the note ID
            noteLink.on('click', function(e) {
                e.preventDefault();
                note_detail(note.id);

                // Highlight the note in the directory
                $('.note').removeClass('note-highlight');
                noteListItem.addClass('note-highlight');
            });

            noteLink.on('contextmenu', function(e) {
                e.preventDefault();

                let menu = $('<div></div>').addClass('dropdown-menu show').css({
                    position: 'absolute',
                    left: e.pageX,
                    top: e.pageY
                });

                menu.append($('<a></a>').addClass('dropdown-item').attr('href', '#').text('Copy link').on('click', function (e) {
                    e.preventDefault();
                    copy_object_link(note.id);
                }));

                menu.append($('<a></a>').addClass('dropdown-item').attr('href', '#').text('Copy MD link').on('click', function (e) {
                    e.preventDefault();
                    copy_object_link_md('notes',note.id);
                }));

                menu.append($('<a></a>').addClass('dropdown-item').attr('href', '#').text('Move').on('click', function (e) {
                    e.preventDefault();
                    move_item(note.id, 'note');
                }));

                menu.append($('<div></div>').addClass('dropdown-divider'));
                menu.append($('<a></a>').addClass('dropdown-item text-danger').attr('href', '#').text('Delete').on('click', function (e) {
                    e.preventDefault();
                    delete_note(note.id, cid);
                }));

                $('body').append(menu).on('click', function() {
                    menu.remove();
                });

            });

            noteListItem.append(noteLink);
            notesList.append(noteListItem);
        });
        container.append(notesList);
    }

    return listItem;
}


function handle_ed_paste(event) {
    let filename = null;
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
                    note_editor.insertSnippet(`\n![${filename}](${url} =100%x40%)\n`);
                });

            };
            reader.readAsDataURL(blob);
        } else {
            notify_error('Unsupported direct paste of this item. Use datastore to upload.');
        }
      }
    }
}


function note_interval_pinger() {
    if (new Date() - last_ping > 2000) {
        collaborator_socket.emit('ping-note',
            { 'channel': 'case-' + get_caseid() + '-notes', 'note_id': note_id });
        last_ping = new Date();
    }
}

$(document).ready(function(){

    load_directories().then(
        function() {
            let shared_id = getSharedLink();
            if (shared_id) {
                note_detail(shared_id);
            }

            $('.page-aside').resizable({
                handles: 'e'
            });
        }
    )


    cid = get_caseid();
    collaborator_socket = io.connect();
    collaborator_socket.emit('join-notes-overview', { 'channel': 'case-' + cid + '-notes' });

    collaborator_socket.on('ping-note', function(data) {
        last_ping = new Date();

        // Set as int to avoid type mismatch
        if (parseInt(data.note_id) !== parseInt(note_id)) return;

        ppl_viewing.set(data.user, 1);
        for (let [key, value] of ppl_viewing) {
            if (key !== data.user) {
                ppl_viewing.set(key, value-1);
            }
            if (value < 0) {
                ppl_viewing.delete(key);
            }
        }
        refresh_ppl_list(session_id, note_id);
    });

    timer_socket = setInterval( function() {
        note_interval_pinger();
    }, 2000);

    collaborator_socket.emit('ping-note', { 'channel': 'case-' + cid + '-notes', 'note_id': note_id });

    setInterval(auto_remove_typing, 1500);

    $(document).on('click', '#currentNoteTitle', function() {
        let title = $(this).text();

        let input = $('<input>');
        input.attr('id', 'currentNoteTitleInput');
        input.attr('type', 'text');
        input.val(title);
        input.addClass('form-control');

        $(this).replaceWith(input);

        $('#currentNoteTitleInput').focus();
    });

    $(document).on('blur', '#currentNoteTitleInput', function(e) {
        let title = $(this).val();

        let h4 = $('<h4>');
        h4.attr('id', 'currentNoteTitle');
        h4.addClass('page-title mb-0');
        h4.text(title);

        $(this).replaceWith(h4);

        save_note();
    });

    $('#search-input').keyup(function() {
        let searchInput = $(this).val();
        fetchNotes(searchInput);
    });

    $('#clear-search').on('click', function() {
        // Clear the search input field
        $('#search-input').val('');

        $('.directory-container').find('li').show();
        $('.directory').show();
        $('.note').show();
    });

});
