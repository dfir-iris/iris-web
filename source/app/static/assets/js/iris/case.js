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

function do_deletion_prompt(message) {
    if (has_deletion_prompt) {
            return new Promise((resolve, reject) => {
                swal({
                    title: "Are you sure?",
                    text: message,
                    icon: "warning",
                    buttons: true,
                    dangerMode: true,
                    confirmButtonColor: '#3085d6',
                    cancelButtonColor: '#d33',
                    confirmButtonText: 'Confirm'
                })
                .then((willDelete) => {
                    if (willDelete) {
                        resolve();
                    } else {
                        if (reject !== undefined) {
                            reject();
                        }
                        return;
                    }
                });
            });
    } else {
        return new Promise((resolve, reject) => {
            resolve();
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