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

function remove_case(id) {

    swal({
      title: "Are you sure?",
      text: "You won't be able to revert this !\nAll associated data - except Pigger DBs - will be deleted",
      icon: "warning",
      buttons: true,
      dangerMode: true,
      confirmButtonColor: '#3085d6',
      cancelButtonColor: '#d33',
      confirmButtonText: 'Yes, delete it!'
    })
    .then((willDelete) => {
      if (willDelete) {
          $.ajax({
              url: '/manage/cases/delete/' + id,
              type: "POST",
              dataType: 'JSON',
              success: function (data) {
                  if (data.status == 'success') {
                      swal("Case has been deleted !", {
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
      } else {
        swal("Pfew, that's was close");
      }
    });
}

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