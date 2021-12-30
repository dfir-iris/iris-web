const preventFormDefaultBehaviourOnSubmit = (event) => {
    event.preventDefault();
    return false;
};

function add_customer() {
    const url = 'customers/add/modal' + case_param();
    $('#modal_add_customer_content').load(url, function () {
        $('#form_new_customer').on("submit", preventFormDefaultBehaviourOnSubmit);
        $('#submit_new_customer').on("click", function () {
            const form = $('#form_new_customer').serializeObject();

            $.ajax({
                url: 'customers/add' + case_param(),
                type: "POST",
                data: JSON.stringify(form),
                dataType: "json",
                contentType: "application/json;charset=UTF-8",
                cache: false,
                success: function (data) {
                    if (data.status == 'success') {
                        swal(
                            "Done !",
                            "Your customer has been created successfully",
                            {
                                icon: "success",
                                timer: 2000
                            }
                        ).then((value) => {
                            refresh_customer_table();
                            $('#modal_add_customer').modal('hide');

                        });
                    } else {
                        $('#modal_add_customer').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    propagate_form_api_errors(error.responseJSON.data);
                }
            });

            return false;
        })
    });
    $('#modal_add_customer').modal({show: true});
}

$('#customers_table').dataTable({
        "ajax": {
            "url": "customers/list" + case_param(),
            "contentType": "application/json",
            "type": "GET",
            "data": function (d) {
                if (d.status == 'success') {
                    return JSON.stringify(d.data);
                } else {
                    return [];
                }
            }
        },
        "order": [[0, "desc"]],
        "autoWidth": false,
        "columnDefs": [
            {
                "render": function (data, type, row) {
                    data = sanitizeHTML(data);
                    return '<a href="#" onclick="customer_detail(\'' + row[1] + '\');">' + data + '</a>';
                },
                "targets": 0
            }
        ]
    }
);

function refresh_customer_table() {
    $('#customers_table').DataTable().ajax.reload();
    notify_success("Refreshed");
}


/* Fetch the details of an asset and allow modification */
function customer_detail(customer_id) {
    url = 'customers/update/' + customer_id + '/modal' + case_param();
    $('#modal_add_customer_content').load(url, function () {

        $('#form_new_customer').on("submit", preventFormDefaultBehaviourOnSubmit);
        $('#submit_new_customer').on("click", function () {
            const form = $('#form_new_customer').serializeObject();

            $.ajax({
                url: 'customers/update/' + customer_id + case_param(),
                type: "POST",
                data: JSON.stringify(form),
                dataType: "json",
                contentType: "application/json;charset=UTF-8",
                success: function (data) {
                    if (data.status == 'success') {
                        swal("You're set !",
                            "The customer has been updated successfully",
                            {
                                icon: "success",
                                timer: 1500
                            }
                        ).then((value) => {
                            refresh_customer_table();
                            $('#modal_add_customer').modal('hide');
                        });

                    } else {
                        $('#modal_add_customer').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    notify_error(error.responseJSON.message);
                }
            });

            return false;
        })


    });
    $('#modal_add_customer').modal({show: true});
}

function delete_customer(id) {
    swal({
        title: "Are you sure?",
        text: "You won't be able to revert this !",
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
                    url: '/manage/customers/delete/' + id + case_param(),
                    type: "GET",
                    dataType: 'JSON',
                    success: function (data) {
                        if (data.status == 'success') {
                            swal("Customer deleted !", {
                                icon: "success",
                                timer: 500
                            }).then((value) => {
                                refresh_customer_table();
                                $('#modal_add_customer').modal('hide');
                            });
                        } else {
                            swal("Oh no !", data.message, "error");
                        }
                    },
                    error: function (error) {
                        swal({title: "Error !",
                              text: error.responseJSON.message,
                              icon: "error"});
                    }
                });
            } else {
                swal("Pfew, that's was close");
            }
        });
}