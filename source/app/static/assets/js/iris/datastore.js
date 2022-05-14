
function load_datastore() {
    get_request_api('/datastore/list/tree')
    .done(function (data){
        if(notify_auto_api(data, true)){
            show_datastore();
        }
    });
}

function show_datastore() {
    $('html').addClass('ds_sidebar_open');
    $('.ds-sidebar-toggler').addClass('toggled');
}

function hide_datastore() {
    $('html').removeClass('ds_sidebar_open');
    $('.ds-sidebar-toggler').removeClass('toggled');
}

