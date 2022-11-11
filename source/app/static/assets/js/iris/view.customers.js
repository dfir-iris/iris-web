
function load_customer_stats(customer_id) {
    get_request_api('/manage/customers/' + customer_id + '/cases')
    .done((data) => {
        if(notify_auto_api(data, true)) {
            $('#last_month_cases').text(data.data.stats.cases_last_month);
            $('#last_year_cases').text(data.data.stats.cases_last_year);
            $('#cases_rolling_week').text(data.data.stats.cases_rolling_week);
            $('#cases_rolling_month').text(data.data.stats.cases_rolling_month);
            $('#cases_rolling_year').text(data.data.stats.cases_rolling_year);
            $('#current_open_cases').text(data.data.stats.open_cases);
            $('#cases_total').text(data.data.stats.cases_total);
            $('#last_year').text(data.data.stats.last_year);
        }
    });
}

$(document).ready(function() {

    customer_id = $('#customer_id').val();
    load_customer_stats(customer_id);

});