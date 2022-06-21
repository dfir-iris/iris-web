var modal_org_table;
var current_orgs_list;
manage_orgs_table = $('#org_table').dataTable( {
    "order": [[ 1, "asc" ]],
    "autoWidth": false,
    "columns": [
        {
            "data": "org_id",
            "render": function ( data, type, row ) {
                if (type === 'display') {
                    data = sanitizeHTML(data)
                    return '<a href="#" onclick="org_detail(\'' + row["org_id"] + '\');">' + data +'</a>';
                }
                return data;
            }
        },
        { "data": "org_name",
          "render": function ( data, type, row ) {
                if (type === 'display') {
                    data = sanitizeHTML(data)
                    return '<a href="#" onclick="org_detail(\'' + row["org_id"] + '\');">' + data +'</a>';
                }
                return data;
            }
        },
        { "data": "org_description",
          "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
        },
        { "data": "org_nationality",
          "render": function (data, type, row, meta) {
                if (type === 'display') {
                    data = sanitizeHTML(data);
                }
                return data;
              }
        },
        { "data": "org_sector",
            "render": function ( data, type, row ) {
                if (type === 'display') {
                    data = sanitizeHTML(data);
                }
                return data;
            }
        }
      ]
    }
);

function refresh_organisations(do_notify) {

    get_request_api('organisations/list')
    .done((data) => {
        if(notify_auto_api(data, true)) {
            current_orgs_list = data.data;
            manage_orgs_table.api().clear().rows.add(data.data).draw();

            if (do_notify !== undefined) {
                notify_success("Refreshed");
            }

        }

    });

}

function org_detail(org_id) {
    url = 'organisations/' + org_id + '/modal' + case_param();
    $('#modal_access_control').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_org').on("click", function () {
            clear_api_error();

            var data_sent = $('#form_new_org').serializeObject();
            post_request_api('/manage/organisations/update/' + org_id, JSON.stringify(data_sent), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_organisations();
                    $('#modal_access_control').modal('hide');
                }
            });

            return false;
        })


    });
    $('#modal_access_control').modal({ show: true });
}

function add_organisation() {
    url = '/manage/organisations/add/modal' + case_param();
    $('#modal_access_control').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_org').on("click", function () {
             clear_api_error();
            var data_sent = $('#form_new_org').serializeObject();
            post_request_api('/manage/organisations/add', JSON.stringify(data_sent), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_organisations();
                    $('#modal_access_control').modal('hide');
                }
            });
        });
        $('#modal_access_control').modal({ show: true });
    });
}

function delete_org(org_id) {

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
        get_request_api('/manage/organisations/delete/' + org_id)
        .done((data) => {
            if(notify_auto_api(data)) {
                refresh_organisations();
                $('#modal_access_control').modal('hide');
            }
        });
      } else {
        swal("Pfew, that was close");
      }
    });
}

function remove_members_from_org(org_id, user_id, on_finish) {

    swal({
      title: "Are you sure?",
      text: "This will remove the user from the organisation",
      icon: "warning",
      buttons: true,
      dangerMode: true,
      confirmButtonColor: '#3085d6',
      cancelButtonColor: '#d33',
      confirmButtonText: 'Yes, remove it!'
    })
    .then((willDelete) => {
        if (willDelete) {
            url = '/manage/organisations/' + org_id + '/members/delete/' + user_id;

            get_request_api(url)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_organisations();
                    refresh_organisation_members(org_id);

                    if (on_finish !== undefined) {
                        on_finish();
                    }

                }
            });
        }
    });

}

function manage_organisation_members(org_id) {
    url = 'organisations/' + org_id + '/members/modal' + case_param();

    $('#manage_org_members_button').text('Loading manager...');

    $('#modal_ac_additional').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             $('#manage_org_members_button').text('Manage');
             return false;
        }

        $('#manage_org_members_button').text('Manage');
        $('#save_org_members').on("click", function () {
            clear_api_error();

            var data_sent = Object();
            data_sent['org_members'] = $('#org_members').val();
            data_sent['csrf_token'] = $('#csrf_token').val();

            post_request_api('organisations/' + org_id + '/members/update', JSON.stringify(data_sent), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_organisations();
                    refresh_organisation_members(org_id);
                    $('#modal_ac_additional').modal('hide');
                }
            });

            return false;
        });
        $('#modal_ac_additional').modal({ show: true });
    });
}

function refresh_organisation_members(org_id) {
    if (modal_org_table !== undefined) {
        get_request_api('/manage/organisations/' + org_id)
        .done((data) => {
            if(notify_auto_api(data)) {
                modal_org_table.clear();
                modal_org_table.rows.add(data.data.org_members).draw();
            }
        });
    }
}

$(document).ready(function () {
    refresh_organisations();
});