let current_users_list = [];
let current_customers_list = [];
let data_dc = [];

function add_user() {
    url = 'users/add/modal' + case_param();
    $('#modal_access_control').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_user').on("click", function () {

            var data_sent = $('#form_new_user').serializeObject()
            clear_api_error();

            post_request_api('users/add', JSON.stringify(data_sent), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_users();
                    $('#modal_access_control').modal('hide');
                }
            });

            return false;
        })
    });
    $('#modal_access_control').modal({ show: true });
}

manage_users_table = $('#users_table').dataTable( {
    "order": [[ 1, "asc" ]],
    "autoWidth": false,
    "language": {
        "emptyTable": "Loading users..."
    },
    "columns": [
        {
            "data": "user_id",
            "render": function ( data, type, row ) {
                if (type === 'display') {
                    data = sanitizeHTML(data)
                    return '<a href="#" onclick="user_detail(\'' + row["user_id"] + '\');">' + data +'</a>';
                }
                return data;
            }
        },
        { "data": "user_name",
          "render": function ( data, type, row ) {
                if (type === 'display') {
                    data = sanitizeHTML(data)
                    return '<a href="#" onclick="user_detail(\'' + row["user_id"] + '\');">' + data +'</a>';
                }
                return data;
            }
        },
        { "data": "user_login",
          "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
        },
        { "data": "user_email",
          "render": function (data, type, row, meta) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
              }
        },
        { "data": "user_active",
        "render": function (data, type, row, meta) {
            if (type === 'display') {
                if (data == true) {
                    data = '<span class="badge ml-2 badge-success">Active</span>';
                } else {
                    data = '<span class="badge ml-2 badge-warning">Disabled</span>';
                }
            }
            return data;
          }
        },
        { "data": "user_is_service_account",
        "render": function (data, type, row, meta) {
            if (type === 'display') {
                if (data == true) {
                    data = '<i class="fa fa-check text-success"></i>';
                } else {
                    data = '<i class="fa fa-xmark text-danger"></i>';
                }
            }
            return data;
          }
        }
      ]
    }
);

function refresh_users(do_notify) {

    get_request_api('users/list')
    .done((data) => {

        if(notify_auto_api(data, true)) {
            current_users_list = data.data;
            manage_users_table.api().clear().rows.add(data.data).draw();

            if (do_notify !== undefined) {
                notify_success("Refreshed");
            }

        }

    });

}




/* Fetch the details of an user and allow modification */
function user_detail(user_id, goto_tab) {
    url = 'users/' + user_id + '/modal' + case_param();
    $('#modal_access_control').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_user').on("click", function () {
            clear_api_error();

            var data_sent = $('#form_new_user').serializeObject();
            post_request_api('/manage/users/update/' + user_id, JSON.stringify(data_sent), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_users();
                    $('#modal_access_control').modal('hide');
                }
            });

            return false;
        })
        if (goto_tab !== undefined) {
            $('.nav-pills a[href="#'+ goto_tab +'"]').tab('show');
        }
        $('#modal_access_control').modal({ show: true });
    });

}

function refresh_user_ac(user_id) {
    var ori_txt = $('#users_refresh_ac_btn').text();
    $('#users_refresh_ac_btn').text('Refreshing..');
    get_request_api('/manage/access-control/recompute-effective-user-ac/' + user_id)
    .done((data) => {
        notify_auto_api(data);
    }).always(() => {
        $('#users_refresh_ac_btn').text(ori_txt);
    });
}

function reset_user_mfa(user_id) {
    let users_refresh_mfa_btn = $('#users_refresh_mfa_btn');
    let ori_txt = users_refresh_mfa_btn.text();
    users_refresh_mfa_btn.text('Resetting..');
    get_request_api('/manage/access-control/reset-mfa/' + user_id)
    .done((data) => {
        notify_auto_api(data);
    }).always(() => {
        users_refresh_mfa_btn.text(ori_txt);
    });
}

function renew_api_for_user(user_id) {
    var ori_txt = $('#users_renew_api_btn').text();
    $('#users_renew_api_btn').text('Renewing..');
    post_request_api('/manage/users/renew-api-key/' + user_id)
    .done((data) => {
        if (notify_auto_api(data)) {
            $('#userApiKey').val(data.data.api_key);
        }
    }).always(() => {
        $('#users_renew_api_btn').text(ori_txt);
    });
}


function delete_user(id) {

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
        var data_sent = {
            'csrf_token': $('#csrf_token').val()
        }
        post_request_api('/manage/users/delete/' + id, JSON.stringify(data_sent))
        .done((data) => {
            if(notify_auto_api(data)) {
                refresh_users();
                $('#modal_access_control').modal('hide');
            }
        });
      } else {
        swal("Pfew, that was close");
      }
    });
}

function activate_user(user_id) {
  get_request_api('/manage/users/activate/' + user_id)
  .done((data) => {
    if(notify_auto_api(data)) {
        user_detail(user_id);
        refresh_users();
    }
  });
}

function deactivate_user(user_id) {
  get_request_api('/manage/users/deactivate/' + user_id)
  .done((data) => {
    if(notify_auto_api(data)) {
        user_detail(user_id);
        refresh_users();
    }
  });
}

function remove_member_from_org_wrap(org_id, user_id) {
    remove_members_from_org(org_id, user_id, function() {
        user_detail(user_id, 'user_orgs_tab');
    });
}

function remove_member_from_group_wrap(group_id, user_id) {
    remove_members_from_group(group_id, user_id, function() {
        user_detail(user_id, 'user_groups_tab');
    });
}

function manage_user_groups(user_id) {
    let url = 'users/' + user_id + '/groups/modal' + case_param();
    $('#modal_ac_additional').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        $('#modal_ac_additional').modal({ show: true });

        $('#save_user_groups_membership').on("click", function () {
            clear_api_error();

            let data_sent = Object();
            data_sent['groups_membership'] = $('#user_groups_membership').val();
            data_sent['csrf_token'] = $('#csrf_token').val();

            post_request_api('/manage/users/' + user_id + '/groups/update', JSON.stringify(data_sent))
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_groups();
                    user_detail(user_id, 'user_groups_tab');
                }
            });
        });
    });
}

function update_customers_membership_modal(user_customers) {
    for (let index in current_customers_list) {
        data_dc.push({
            label: current_customers_list[index].customer_name,
            value: current_customers_list[index].customer_id
        });
    }

    let us_customer = $('#user_customers_membership');

    us_customer.multiselect({
        buttonWidth: 400,
        nonSelectedText: 'Select customers',
        includeSelectAllOption: true,
        enableFiltering: true,
        enableCaseInsensitiveFiltering: true,
        filterPlaceholder: 'Search',
        filterBehavior: 'both',
        widthSynchronizationMode: 'ifPopupIsSmaller'
    });

    us_customer.multiselect('dataprovider', data_dc );

    us_customer.multiselect('select', user_customers);

    us_customer.multiselect('refresh')
}


async function refresh_customers() {
    await get_request_api('customers/list')
    .done((data) => {
        if(notify_auto_api(data, true)) {
            current_customers_list = data.data;
        }
    });
}

function manage_user_clients(user_id) {
    let url = 'users/' + user_id + '/customers/modal' + case_param();
    $('#modal_ac_additional').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        $('#modal_ac_additional').modal({ show: true });

        $('#save_user_customers_membership').on("click", function () {
            clear_api_error();

            let data_sent = Object();
            data_sent['customers_membership'] = $('#user_customers_membership').val();
            data_sent['csrf_token'] = $('#csrf_token').val();

            post_request_api('/manage/users/' + user_id + '/customers/update', JSON.stringify(data_sent))
            .done((data) => {
                if(notify_auto_api(data)) {
                    user_detail(user_id, 'user_clients_tab');
                }
            });
        });
    });

}


function manage_user_organisations(user_id) {
    url = 'users/' + user_id + '/organisations/modal' + case_param();
    $('#modal_ac_additional').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        $('#modal_ac_additional').modal({ show: true });

        $('#save_user_orgs_membership').on("click", function () {
            clear_api_error();

            var data_sent = Object();
            data_sent['orgs_membership'] = $('#user_orgs_membership').val();
            data_sent['csrf_token'] = $('#csrf_token').val();

            post_request_api('/manage/users/' + user_id + '/organisations/update', JSON.stringify(data_sent))
            .done((data) => {
                if(notify_auto_api(data)) {
                    user_detail(user_id, 'user_orgs_tab');
                }
            });
        });
    });
}

function refresh_user_cac(user_id) {
    if (modal_user_cac_table !== undefined) {
        get_request_api('/manage/users/' + user_id)
        .done((data) => {
            if(notify_auto_api(data)) {
                current_user_cases_access_list = data.data.user_cases_access;
                modal_user_cac_table.clear();
                modal_user_cac_table.rows.add(current_user_cases_access_list).draw();
            }
        });
    }
}



function manage_user_cac(user_id) {
    url = 'users/' + user_id + '/cases-access/modal' + case_param();

    $('#manage_user_cac_button').text('Loading manager...');

    $('#modal_ac_additional').load(url, function (response, status, xhr) {
        $('#manage_user_cac_button').text('Set case access');
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#grant_case_access_to_user').on("click", function () {
            clear_api_error();

            var data_sent = Object();

            data_sent['cases_list'] = $('#user_case_access_select').val();
            data_sent['access_level'] = parseInt($('#user_case_ac_select').val());
            data_sent['csrf_token'] = $('#csrf_token').val();

            post_request_api('users/' + user_id + '/cases-access/update', JSON.stringify(data_sent))
            .done((data) => {
                if(notify_auto_api(data)) {
                    refresh_user_cac(user_id);
                    $('#modal_ac_additional').modal('hide');
                }
            });

            return false;
        });
        $('#modal_ac_additional').modal({ show: true });
    });
}


function remove_cases_access_from_user_table(org_id, rows) {
    cases = [];
    for (cid in rows) {
        cases.push(rows[cid].case_id);
    }
    remove_cases_access_user(org_id, cases);
}


$(document).ready(function () {
    refresh_users();
});