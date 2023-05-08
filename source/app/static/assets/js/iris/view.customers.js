
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

$(document).ready(function() {

    customer_id = $('#customer_id').val();
    load_customer_stats(customer_id);

});