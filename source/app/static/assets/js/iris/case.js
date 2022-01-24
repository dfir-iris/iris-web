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
})

function close_case(id) {
  swal({
    title: "Are you sure?",
    text: "Case ID " + id + " will be closed and will not appear in contexts anymore",
    icon: "warning",
    buttons: true,
    dangerMode: true,
    confirmButtonColor: '#3085d6',
    cancelButtonColor: '#d33',
    confirmButtonText: 'Yes, close it!'
  })
  .then((willDelete) => {
    if (willDelete) {
      $.ajax({
          url: '/manage/cases/close/' + id ,
          type: "POST",
          dataType: 'JSON',
          success: function (data) {
              if (data.status == 'success') {
                  swal("Case has been closed !", {
                      icon: "success",
                  }).then((value) => {
                      refresh_case_table();
                      $('#modal_case_detail').modal('hide');
                  });
              } else {
                  swal ( "Oh no !" ,  data.message ,  "error" );
              }
          },
          error: function (error) {
              swal ( "Oh no !" ,  error ,  "error" );                
          }
      });
    }
  });
}

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