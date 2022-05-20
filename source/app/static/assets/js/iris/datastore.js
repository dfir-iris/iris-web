
function load_datastore() {
    get_request_api('/datastore/list/tree')
    .done(function (data){
        if(notify_auto_api(data, true)){
            $('#ds-tree-root').empty();
            build_ds_tree(data.data, 'ds-tree-root');
            reparse_activate_tree();
            show_datastore();
        }
    });
}

function build_ds_tree(data, tree_node) {
    for (node in data) {

        if (data[node] === null) {
            break;
        }

        if (data[node].type == 'directory') {
            data[node].name = sanitizeHTML(data[node].name);
            can_delete = '';
            if (!data[node].is_root) {
                can_delete = `<div class="dropdown-divider"></div><a href="#" class="dropdown-item text-danger" onclick="delete_ds_folder('${node}');"><small class="fa fa-trash mr-2"></small>Delete</a>`;
            }
            jnode = `<li>
                    <span><i class="fa-regular fa-folder"></i> ${data[node].name}</span> <i class="fas fa-plus ds-folder-menu" role="menu" style="cursor:pointer;" data-toggle="dropdown" aria-expanded="false"></i>
                        <div class="dropdown-menu" role="menu">
                                <a href="#" class="dropdown-item" onclick="add_ds_folder('${node}');return false;"><small class="fa-regular fa-folder mr-2"></small>Add folder</a>
                                <a href="#" class="dropdown-item" onclick="add_ds_file('${node}');return false;"><small class="fa-regular fa-file mr-2"></small>Add file</a>
                                <a href="#" class="dropdown-item" onclick="rename_ds_folder('${node}', '${data[node].name}');return false;"><small class="fa-solid fa-pencil mr-2"></small>Rename folder</a>
                                ${can_delete}
                        </div>
                    <ul id='tree-${node}'></ul>
                </li>`;
            $('#'+ tree_node).append(jnode);
            build_ds_tree(data[node].children, 'tree-' + node);
        } else {
            data[node].file_original_name = sanitizeHTML(data[node].file_original_name);
            jnode = `<li>
                <span><i class="fa-regular fa-file" role="menu" style="cursor:pointer;" data-toggle="dropdown" aria-expanded="false"></i> ${data[node].file_original_name}
                        <div class="dropdown-menu" role="menu">
                                <a href="#" class="dropdown-item" onclick="copy_object_link('${node}');return false;"><small class="fa fa-share mr-2"></small>Get link</a>
                                <a href="#" class="dropdown-item" onclick="duplicate_event('${node}');return false;"><small class="fa fa-clone mr-2"></small>Duplicate</a>
                                <div class="dropdown-divider"></div>
                                <a href="#" class="dropdown-item text-danger" onclick="delete_ds_file('${node}');"><small class="fa fa-trash mr-2"></small>Delete</a>
                        </div>
                    </span>
                </li>`;
            $('#'+ tree_node).append(jnode);
        }
    }
}

function show_datastore() {
    $('html').addClass('ds_sidebar_open');
    $('.ds-sidebar-toggler').addClass('toggled');
}

function hide_datastore() {
    $('html').removeClass('ds_sidebar_open');
    $('.ds-sidebar-toggler').removeClass('toggled');
}

function reparse_activate_tree() {
    $('.tree li:has(ul)').addClass('parent_li').find(' > span').attr('title', 'Collapse this branch');
    $('.tree li.parent_li > span').on('click', function (e) {
        var children = $(this).parent('li.parent_li').find(' > ul > li');
        if (children.is(":visible")) {
            children.hide('fast');
            $(this).attr('title', 'Expand this branch').find(' > i').addClass('icon-plus-sign').removeClass('icon-minus-sign');
        } else {
            children.show('fast');
            $(this).attr('title', 'Collapse this branch').find(' > i').addClass('icon-minus-sign').removeClass('icon-plus-sign');
        }
        e.stopPropagation();
    });
}

function add_ds_folder(parent_node) {
    $('#ds_mod_folder_name').data('parent-node', parent_node);
    $('#ds_mod_folder_name').data('node-update', false);
    $('#ds_mod_folder_name').val('');
    $('#modal_ds_folder').modal("show");
}

function rename_ds_folder(parent_node, name) {
    $('#ds_mod_folder_name').data('parent-node', parent_node);
    $('#ds_mod_folder_name').data('node-update', true);
    $('#ds_mod_folder_name').val(name);
    $('#modal_ds_folder').modal("show");
}

function delete_ds_folder(node) {
    node = node.replace('d-', '');
    swal({
        title: "Are you sure?",
        text: "This will delete all files included and sub-folders",
        icon: "warning",
        buttons: true,
        dangerMode: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, delete it!'
    })
    .then((willDelete) => {
        if (willDelete) {
            get_request_api('/datastore/folder/delete/' + node)
            .done((data) => {
                if (notify_auto_api(data)) {
                    load_datastore();
                }
            });
        } else {
            swal("Pfew, that was close");
        }
    });
}

function save_ds_mod_folder() {
    var data = Object();

    data['parent_node'] = $('#ds_mod_folder_name').data('parent-node').replace('d-', '');
    data['folder_name'] =  $('#ds_mod_folder_name').val();
    data['csrf_token'] = $('#csrf_token').val();

    if ($('#ds_mod_folder_name').data('node-update')) {
        uri = '/datastore/folder/rename/' + data['parent_node'];
    } else {
        uri = '/datastore/folder/add';
    }

    post_request_api(uri, JSON.stringify(data))
    .done(function (data){
        if(notify_auto_api(data)){
            $('#modal_ds_folder').modal("hide");
            load_datastore();
        }
    });
}

function add_ds_file(node) {
    node = node.replace('d-', '');
    url = '/datastore/file/add/'+ node +'/modal' + case_param();
    $('#modal_ds_file_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#modal_ds_file').modal("show");
    });
}

function save_ds_file(node) {
    var formData = new FormData($('#form_new_ds_file')[0]);
    formData.append('file_content', $('#input_upload_ds_file').prop('files')[0]);

    post_request_data_api('/datastore/file/add/' + node, formData, true)
    .done(function (data){
        if(notify_auto_api(data)){
            $('#modal_ds_file').modal("hide");
            load_datastore();
        }
    })
}

function delete_ds_file(file_id) {
    file_id = file_id.replace('f-', '');
    swal({
        title: "Are you sure?",
        text: "This will delete the file on the server and any manual reference will become invalid",
        icon: "warning",
        buttons: true,
        dangerMode: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, delete it!'
    })
    .then((willDelete) => {
        if (willDelete) {
            get_request_api('/datastore/file/delete/' + file_id)
            .done((data) => {
                if (notify_auto_api(data)) {
                    load_datastore();
                }
            });
        } else {
            swal("Pfew, that was close");
        }
    });
}