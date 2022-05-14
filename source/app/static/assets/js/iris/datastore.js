
function load_datastore() {
    get_request_api('/datastore/list/tree')
    .done(function (data){
        if(notify_auto_api(data, true)){

            build_ds_tree(data.data, 'ds_tree_root');
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
            console.log(data[node].name);
            jnode = `<li>
                    <span><i class="fa-solid fa-folder mr-1"></i> ${data[node].name}</span><a href=""></a>
                    <ul id='tree-${node}'></ul>
                </li>`;
            $('#'+ tree_node).append(jnode);
            build_ds_tree(data[node].children, 'tree-' + node);
        } else {
            jnode = `<li><span><i class="fa-solid fa-file mr-1"></i> ${data[node].data_original_filename}</span><a href=""></a></li>`;
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