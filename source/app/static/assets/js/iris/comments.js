var g_comment_desc_editor = null;
function comment_element(element_id, element_type, is_alert=false) {

    const prefix = is_alert ? '/alerts' : `/case/${element_type}`;
    const url = `${prefix}/${element_id}/comments/modal`;
    $('#modal_comment_content').load(url + case_param(),
        function (response, status, xhr) {
            if (status !== "success") {
                 ajax_notify_error(xhr, url);
                 return false;
            }

            $('#modal_comment_content').resizable({
                minHeight: 300,
                minWidth: 300,
                handles: "n, e, s, w, ne, se, sw, nw"
            });
            $('.modal-comment').draggable({
                cursor: 'move'
            });

            $('#modal_comment').modal('show');

            g_comment_desc_editor = get_new_ace_editor('comment_message', 'comment_content', 'target_comment_content',
                        function() {
                            $('#last_saved').addClass('btn-danger').removeClass('btn-success');
                            $('#last_saved > i').attr('class', "fa-solid fa-file-circle-exclamation");
                        }, null, false, false);

            headers = get_editor_headers('g_comment_desc_editor', null, 'comment_edition_btn');
            $('#comment_edition_btn').append(headers);

            load_comments(element_id, element_type, undefined, undefined, is_alert);
        }
    );
}

function preview_comment() {
    if(!$('#container_comment_preview').is(':visible')) {
        let comment_text = g_comment_desc_editor.getValue();
        let converter = get_showdown_convert();
        let html = converter.makeHtml(comment_text);
        let comment_html = do_md_filter_xss(html);
        $('#target_comment_content').html(comment_html);
        $('#container_comment_preview').show();
        $('#comment_preview_button').html('<i class="fa-solid fa-eye-slash"></i> Edit');
        $('#container_comment_content').hide();
    }
    else {
        $('#container_comment_preview').hide();
        $('#comment_preview_button').html('<i class="fa-solid fa-eye"></i> Preview');
        $('#container_comment_content').show();
    }
}

function save_comment(element_id, element_type) {
    save_comment_ext(element_id, element_type, false);
}

function save_comment_ext(element_id, element_type, do_close){
    data = Object();
    data['comment_text'] = g_comment_desc_editor.getValue();
    data['csrf_token'] = $('#csrf_token').val();
    const is_alert = element_type === 'alerts';
    const prefix = is_alert ? '/alerts' : `/case/${element_type}`;

    post_request_api(`${prefix}/${element_id}/comments/add`, JSON.stringify(data), true)
    .done((data) => {
        if(notify_auto_api(data)) {
            load_comments(element_id, element_type, undefined, undefined, is_alert);
            g_comment_desc_editor.setValue('');
            increase_modal_comments_count(element_type, element_id);
        }
    });
}

function decrease_modal_comments_count(element_type, element_id) {

    let tid = '#object_comments_number';
    if (element_type === 'timeline/events' || element_type === 'alerts') {
        tid = '#object_comments_number_' + element_id;
    }

    let curr_count = $(tid).text();

    if (curr_count > 0) {
        $(tid).text(curr_count - 1);
        if (element_type === 'timeline/events' || element_type === 'alerts') {
            $('#object_comments_number').text(parseInt(curr_count) - 1);
        }
    }

}

function increase_modal_comments_count(element_type, element_id) {
    let tid = '#object_comments_number';
    if (element_type === 'timeline/events' || element_type === 'alerts') {
        tid = '#object_comments_number_' + element_id;
    }

    let curr_count = $(tid).text();
    if (curr_count === '') {
        curr_count = 0;
    }

    $(tid).text(parseInt(curr_count) + 1);
    if (element_type === 'timeline/events' || element_type === 'alerts') {
        $('#object_comments_number').text(parseInt(curr_count) + 1);
    }
}

function delete_comment(comment_id, element_id, element_type) {
    do_deletion_prompt("You are about to delete comment #" + comment_id)
    .then((doDelete) => {
        if (doDelete) {
            data = Object();
            data['csrf_token'] = $('#csrf_token').val();

            const is_alert = element_type === 'alerts';
            const prefix = is_alert ? '/alerts' : `/case/${element_type}`;
            post_request_api(`${prefix}/${element_id}/comments/${comment_id}/delete`, JSON.stringify(data))
            .done((data) => {
                if(notify_auto_api(data)) {
                    load_comments(element_id, element_type, undefined, undefined, is_alert);
                    decrease_modal_comments_count(element_type, element_id);
                }
            });
        }
    });
}

function edit_comment(comment_id, element_id, element_type) {
    const is_alert = element_type === 'alerts';
    const prefix = is_alert ? '/alerts' : `/case/${element_type}`;
    get_request_api(`${prefix}/${element_id}/comments/${comment_id}`)
    .done((data) => {
        if(notify_auto_api(data, true)) {

            $('#comment_'+comment_id).addClass('comment_editing');
            $('#comment_'+comment_id).data('comment_id', comment_id);
            g_comment_desc_editor.setValue(data.data.comment_text);
            $('#comment_edition').show();
            $('#comment_submit').hide();
            $('#cancel_edition').show();

        }
    });

}

function save_edit_comment(element_id, element_type) {
    data = Object();
    data['comment_text'] = g_comment_desc_editor.getValue();
    comment_id = $('.comment_editing').data('comment_id');
    data['csrf_token'] = $('#csrf_token').val();

    const is_alert = element_type === 'alerts';
    const prefix = is_alert ? '/alerts' : `/case/${element_type}`;
    post_request_api(`${prefix}/${element_id}/comments/${comment_id}/edit`, JSON.stringify(data), true)
    .done((data) => {
        if(notify_auto_api(data)) {
            cancel_edition(comment_id);
            load_comments(element_id, element_type, comment_id, undefined, is_alert);
        }
    });
}

function cancel_edition(comment_id) {
    $('.comment_editing').css('background-color', '');
    $('.comment_editing').css('border-radius', '');
    $('.comment_editing').removeClass('comment_editing');
    $('.comment_editing').data('comment_id', '');
    $('#comment_edition').hide();
    $('#cancel_edition').hide();
    $('#comment_submit').show();
    g_comment_desc_editor.setValue('');
}

function load_comments(element_id, element_type, comment_id, do_notification, is_alert=false) {

    if (do_notification !== undefined) {
        silent_success = !do_notification;
    } else {
        silent_success = true;
    }

    const prefix = is_alert || element_type === 'alerts' ? '/alerts' : `/case/${element_type}`;

    get_request_api(`${prefix}/${element_id}/comments/list`)
    .done((data) => {
        if (notify_auto_api(data, silent_success)) {
            $('#comments_list').empty();
            var names = Object;
            for (var i = 0; i < data['data'].length; i++) {

                comment_text = data['data'][i].comment_text;
                converter = get_showdown_convert();
                html = converter.makeHtml(do_md_filter_xss(comment_text));
                comment_html = do_md_filter_xss(html);
                const username = data['data'][i].user.user_name;
                if (names.hasOwnProperty(username)) {
                    avatar = names[username];
                } else {
                    avatar = get_avatar_initials(username);
                    names[username] = avatar;
                }

                can_edit = "";
                current_user = $('#current_username').text();

                if (current_user === data['data'][i].user.user_login) {
                    can_edit = '<a href="#" class="btn btn-sm comment-edition-hidden" title="Edit comment" onclick="edit_comment(\'' + data['data'][i].comment_id + '\', \'' + element_id + '\',\''+ element_type +'\'); return false;"><i class="fa-solid fa-edit text-dark"></i></a>';
                    can_edit += '<a href="#" class="btn btn-sm comment-edition-hidden" title="Delete comment" onclick="delete_comment(\'' + data['data'][i].comment_id + '\', \'' + element_id + '\',\''+ element_type +'\'); return false;"><i class="fa-solid fa-trash text-dark"></i></a>';
                }

                comment = `
                    <div class="row mb-2 mr-1" >
                        <div class="col-12" id="comment_${data['data'][i].comment_id}">
                            <div class="row mt-2">
                                <div class="col">
                                    <div class="row mr-2">
                                        <div class="col">
                                            <div class="ml-2 row">
                                                ${avatar}
                                                <h6 class="text-uppercase fw-bold mb-1 ml-1 mt-2">${filterXSS(data['data'][i].name)}</h6>
                                                <div class="ml-auto">
                                                    ${can_edit} <small class="text-muted text-wrap">${data['data'][i].comment_date}</small>
                                                </div>
                                            </div>
                                            <div class="row" style="border-left: 3px solid #eaeaea;margin-left:30px;">
                                                <span class="text-muted ml-2">${comment_html}</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                $('#comments_list').append(comment);
            }
            $('#comments_list').append('<div id="last-comment"><div>');

            if (data['data'].length === 0) {
                $('#comments_list').html('<div class="text-center">No comments yet</div>');
            } else if (comment_id === undefined || comment_id === null) {
                offset = document.getElementById("last-comment").offsetTop;
                if (offset > 20) {
                    $('.comments-listing').animate({ scrollTop: offset});
                }
            } else {
                if (document.getElementById('#comment_'+comment_id) !== null) {
                    offset = document.getElementById('#comment_'+comment_id).offsetTop;
                    if (offset > 20) {
                        $('.comments-listing').animate({ scrollTop: offset});
                    }
                }
            }
        }
    });
}