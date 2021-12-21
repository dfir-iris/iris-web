function backup_db() {
    $.ajax({
        url: '/manage/advanced/backup/db' + case_param(),
        type: "GET",
        dataType: 'JSON',
        beforeSend: function() {
            window.swal({
                title: "Backing-up DB",
                text: "Please wait..",
                buttons: false,
                closeOnClickOutside: false,
                closeOnEsc: false
              });
        },
        complete: function() {
            swal.close();
        },
        success: function (data) {
            if (data.status == 'success') {
                swal("Back-up !", {
                    icon: "success",
                }).then((value) => {
                    refresh_db_table();
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