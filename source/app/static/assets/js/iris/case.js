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
    $('#case_info').show();
    $('#cancel_case_info').hide();
}

function save_case_edit(case_id) {

    var data_sent = $('form#form_update_case').serializeObject();
    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;

    data_sent['csrf_token'] = $('#csrf_token').val();

    post_request_api('/manage/cases/update', JSON.stringify(data_sent), true)
    .done((data) => {
        if(notify_auto_api(data)) {
            case_detail(case_id);
        }
    });
}

function do_deletion_prompt(message) {
    if (has_deletion_prompt) {
            return new Promise((resolve, reject) => {
                swal({
                    title: "Are you sure?",
                    text: message,
                    icon: "warning",
                    buttons: {
                        cancel: {
                            text: "Cancel",
                            value: false,
                            visible: true,
                            closeModal: true
                        },
                        confirm: {
                           text: "Confirm",
                           value: true
                        }
                    },
                    dangerMode: true
                })
                .then((willDelete) => {
                    resolve(willDelete);
                })
                .catch((error) => {
                    reject(error);
                });
            });
    } else {
        return new Promise((resolve, reject) => {
            resolve(true);
        });
    }
}

$(document).ready(function(){
    $(function(){
        var current = location.pathname;
        $('#h_nav_tab li').each(function(){
            var $this = $(this);
            var child = $this.children();
            // if the current path is like this link, make it active
            if(child.attr('href').split("?")[0] == current){
                $this.addClass('active');
                return;
            }
        })
    });
});