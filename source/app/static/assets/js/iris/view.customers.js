let users_table = null;
let cases_table = null;
let assets_table = null;

function delete_contact(contact_id, customer_id) {
    post_request_api('/manage/customers/' + customer_id + '/contacts/' + contact_id + '/delete', null, true)
    .done((data) => {
        if(notify_auto_api(data)) {
            window.location.reload();
        }
    });
}

function edit_contact(contact_id, customer_id) {
    url = '/manage/customers/' + customer_id + '/contacts/' + contact_id + '/modal' + case_param();
    $('#modal_add_contact_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#form_new_contact').on("submit", preventFormDefaultBehaviourOnSubmit);
        $('#submit_new_contact').on("click", function () {

            const form = $('#form_new_contact').serializeObject();

            post_request_api('/manage/customers/' + customer_id + '/contacts/' + contact_id + '/update', JSON.stringify(form), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    window.location.reload();
                }
            });

            return false;
        });


        $('#submit_delete_contact').on("click", function () {
            post_request_api('/manage/customers/' + customer_id + '/contacts/' + contact_id + '/delete')
            .done((data) => {
                if(notify_auto_api(data)) {
                    window.location.reload();
                }
            });
            return false;
        });
    });
    $('#modal_add_contact').modal({show: true});
}

function add_new_contact(customer_id) {
    url = '/manage/customers/' + customer_id + '/contacts/add/modal' + case_param();
    $('#modal_add_contact_content').load(url, function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#form_new_contact').on("submit", preventFormDefaultBehaviourOnSubmit);
        $('#submit_new_contact').on("click", function () {

            const form = $('#form_new_contact').serializeObject();

            post_request_api('/manage/customers/' + customer_id + '/contacts/add', JSON.stringify(form), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    window.location.reload();
                }
            });

            return false;
        })


    });
    $('#modal_add_contact').modal({show: true});
}

function load_customer_stats(customer_id) {
    get_request_api('/manage/customers/' + customer_id + '/cases')
    .done((data) => {
        if(notify_auto_api(data, true)) {
            $('#last_month_cases').text(data.data.stats.cases_last_month);
            $('#last_year_cases').text(data.data.stats.cases_last_year);
            $('#cases_last_month').text(data.data.stats.cases_last_month);
            $('#cases_current_month').text(data.data.stats.cases_current_month);
            $('#cases_current_year').text(data.data.stats.cases_current_year);
            $('#current_open_cases').text(data.data.stats.open_cases);
            $('#cases_total').text(data.data.stats.cases_total);
            $('#ratio_year').text(data.data.stats.ratio_year);
            $('#average_case_duration').text(data.data.stats.average_case_duration);

            if (data.data.stats.ratio_year > 0) {
                $('#ratio_year').addClass('text-warning');
                $('#ratio_year').html(`+${data.data.stats.ratio_year}% <i class="ml-1 fa fa-chevron-up"></i>`);
            } else if (data.data.stats.ratio_year < 0) {
                $('#ratio_year').addClass('text-success');
                $('#ratio_year').html(`${data.data.stats.ratio_year}% <i class="ml-1 fa fa-chevron-down"></i>`);
            }

            if (data.data.stats.ratio_month > 0) {
                $('#ratio_month').addClass('text-warning');
                $('#ratio_month').html(`+${data.data.stats.ratio_month}% <i class="ml-1 fa fa-chevron-up"></i>`);
            } else if (data.data.stats.ratio_month < 0) {
                $('#ratio_month').addClass('text-success');
                $('#ratio_month').html(`${data.data.stats.ratio_month}% <i class="ml-1 fa fa-chevron-down"></i>`);
            }

            $('#last_year').text(data.data.stats.last_year);

        }
    });
}

function refresh_client_users(customer_id) {
    get_raw_request_api(`/manage/users/filter?customer_id=${customer_id}`)
        .done((data) => {
            if (notify_auto_api(data, true)) {
                users_table.api().clear().rows.add(data.data.users).draw();
            }
        })
}

function refresh_client_cases(customer_id) {
    get_raw_request_api(`/manage/cases/filter?case_customer_id=${customer_id}`)
        .done((data) => {
            if (notify_auto_api(data, true)) {
                cases_table.api().clear().rows.add(data.data.cases).draw();
            }
        })

}

$(document).ready(function() {

    let customer_id = $('#customer_id').val();
    load_customer_stats(customer_id);

    $('#collapse_client_users_view').on('show.bs.collapse', function() {
        refresh_client_users(customer_id)
    });

    users_table = $('#client_users_table').dataTable({
        "order": [[ 1, "asc" ]],
        "autoWidth": false,
        "columns": [
            {
                "data": "user_id",
                "render": function(data, type, row) {
                    return data;
                }
            },
            {
                "data": "user_name",
                "render": function(data, type, row) {
                    return data;
                }

            },
            {
                "data": "user_login",
                "render": function(data, type, row) {
                    return data;
                }
            },
            {
                "data": "is_service_account",
                "render": function(data, type, row) {
                    return data;
                }
            }
        ]
    });

    assets_table = $('#client_assets_table').dataTable({
        "order": [[ 1, "asc" ]],
        "autoWidth": false,
        "columns": [
            {
                "data": "asset_name",
                "render": function(data, type, row) {
                    return data;
                }
            },
            {
                "data": "asset_description",
                "render": function(data, type, row) {
                    return data;
                }

            },
            {
                "data": "asset_type",
                "render": function(data, type, row) {
                    return data.asset_name;
                }
            },
            {
                "data": "asset_ip",
                "render": function(data, type, row) {
                    return data;
                }
            },
            {
                "data": "case_id",
                "render": function(data, type, row) {
                    if (type === 'display' && data !== null) {
                        let a_anchor = $('<a></a>');
                        a_anchor.attr('href', '/case?cid=' + data);
                        a_anchor.attr('target', '_blank');
                        a_anchor.attr('rel', 'noopener');
                        a_anchor.text('#' + data);
                        return a_anchor.prop('outerHTML');
                    }
                    return data;
                }
            }
        ],
        "serverSide": true,
        "ajax": {
            "url": "/manage/assets/filter",
            "type": "GET",
            "data": function (d) {
                let page = Math.floor(d.start / d.length) + 1;
                d.page = page;
                d.per_page = d.length;
                d.customer_id = customer_id;
                d.order_by = d.columns[d.order[0].column].data;
                d.sort_dir = d.order[0].dir;
            },
            "dataSrc": function (json) {
                json.recordsTotal = json.data.total;
                json.recordsFiltered = json.data.total;
                json.draw = json.data.draw
                json.data = json.data.assets;

                return json.data;
            }
        }
    });

    cases_table = $('#client_cases_table').dataTable({
        "order": [[ 1, "asc" ]],
        "autoWidth": false,
        "columns": [
            {
                "data": "name",
                "render": function(data, type, row) {
                    if (type === 'display') {
                        let a_anchor = $('<a></a>');
                        a_anchor.attr('href', '/case?cid=' + row['case_id']);
                        a_anchor.attr('target', '_blank');
                        a_anchor.attr('rel', 'noopener');
                        a_anchor.text(data);
                        return a_anchor.prop('outerHTML');
                    }
                    return data;
                }
            },
            {
                "data": "open_date",
                "render": function(data, type, row) {
                    return data;
                }
            },
            {
                "data": "state",
                "render": function(data, type, row) {
                    if (data !== null) {
                        return data.state_name;
                    } else {
                        return 'Unknown';
                    }
                }
            },
            {
                "data": "owner",
                "render": function(data, type, row) {
                    return data.user_name;
                }
            }
        ],
        "serverSide": true,
        "ajax": {
            "url": "/manage/cases/filter",
            "type": "GET",
            "data": function (d) {
                let page = Math.floor(d.start / d.length) + 1;
                d.page = page;
                d.per_page = d.length;
                d.case_customer_id = customer_id;
                d.order_by = d.columns[d.order[0].column].data;
                d.sort_dir = d.order[0].dir;
            },
            "dataSrc": function (json) {
                json.recordsTotal = json.data.total;
                json.recordsFiltered = json.data.total;
                json.draw = json.data.draw
                json.data = json.data.cases;

                return json.data;
            }
        }
    });
});