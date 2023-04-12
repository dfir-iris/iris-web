function buildShareLink(lookup_id) {
    current_path = location.protocol + '//' + location.host + location.pathname;
    current_path = current_path + case_param() + '&shared=' + lookup_id;

    return current_path;
}

function getSharedLink(){
    queryString = window.location.search;
    urlParams = new URLSearchParams(queryString);
    if (Number.isInteger(parseInt(urlParams.get('shared')))) {
        return urlParams.get('shared')
    }
    return null;
}

function edit_case_info() {
    $('#case_gen_info_content').hide();
    $('#case_gen_info_edit').show();
    $('#cancel_case_info').show();
    $('#save_case_info').show();
    $('#case_info').hide();
}

function cancel_case_edit() {
    $('#case_gen_info_content').show();
    $('#case_gen_info_edit').hide();
    $('#cancel_case_info').hide();
    $('#save_case_info').hide();
    $('#case_info').show();
}

function save_case_edit(case_id) {

    var data_sent = $('form#form_update_case').serializeObject();
    var map_protagonists = Object();

    for (e in data_sent) {
        if (e.startsWith('protagonist_role_')) {
            map_protagonists[e.replace('protagonist_role_', '')] = {
                'role': data_sent[e]
            };
            delete data_sent[e];
        }
        if (e.startsWith('protagonist_name_')) {
            map_protagonists[e.replace('protagonist_name_', '')]['name'] = data_sent[e];
            delete data_sent[e];
        }
        if (e.startsWith('protagonist_contact_')) {
            map_protagonists[e.replace('protagonist_contact_', '')]['contact'] = data_sent[e];
            delete data_sent[e];
        }
        if (e.startsWith('protagonist_id_')) {
            map_protagonists[e.replace('protagonist_id_', '')]['id'] = data_sent[e];
            delete data_sent[e];
        }
    }
    data_sent['protagonists'] = [];
    for (e in map_protagonists) {
        data_sent['protagonists'].push(map_protagonists[e]);
    }

    data_sent['case_tags'] = $('#case_tags').val();

    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;

    data_sent['csrf_token'] = $('#csrf_token').val();

    post_request_api('/manage/cases/update/' + case_id, JSON.stringify(data_sent), true)
    .done((data) => {
        if(notify_auto_api(data)) {
            case_detail(case_id);
        }
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
                post_request_api('/manage/cases/delete/' + id)
                .done((data) => {
                    if (notify_auto_api(data)) {
                        $('#modal_case_detail').modal('hide');
                    }
                });
            } else {
                swal("Pfew, that was close");
            }
        });
}

/* Reopen case function */
function reopen_case(id) {
    post_request_api('/manage/cases/reopen/' + id)
    .done((data) => {
        window.location.reload();
        $('#modal_case_detail').modal('hide');
    });
}

/* Close case function */
function close_case(id) {
    swal({
        title: "Are you sure?",
        text: "Case ID " + id + " will be closed",
        icon: "warning",
        buttons: true,
        dangerMode: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, close it!'
    })
    .then((willClose) => {
        if (willClose) {
            post_request_api('/manage/cases/close/' + id)
            .done((data) => {
                window.location.reload();
                $('#modal_case_detail').modal('hide');
            });
        }
    });
}

function add_protagonist() {
    random_string = Math.random().toString(36).substring(7);
    prota_html = $('#protagonist_list_edit_template').html();
    prota_html = prota_html.replace(/__PROTAGONIST_ID__/g, random_string);
    $('#protagonist_list_edit').append(prota_html);
}

function remove_protagonist(id) {
    $('#protagonist_' + id).remove();
}


$(document).ready(function(){
    $(function(){
        var current = location.pathname;
        $('#h_nav_tab li').each(function(){
            var $this = $(this);
            var child = $this.children();
            // if the current path is like this link, make it active
            if(child.attr('href') !== undefined && child.attr('href').split("?")[0] == current){
                $this.addClass('active');
                return;
            }
        })
    });

    $('#case_quick_status').change(function(){
        post_request_api('/case/update-status', JSON.stringify({
            'status_id': $('#case_quick_status').val(),
            'csrf_token': $('#csrf_token').val()
        }))
        .done((data) => {
            if (notify_auto_api(data)) {
                window.location.reload();
            }
        })
    });
});