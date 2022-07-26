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