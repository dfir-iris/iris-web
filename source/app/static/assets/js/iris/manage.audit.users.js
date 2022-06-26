
url = '/manage/access-control/audit/users/9/modal' + case_param()
$('#user_audit_content').load(url, function (response, status, xhr) {
    hide_minimized_modal_box();
    if (status !== "success") {
         ajax_notify_error(xhr, url);
         return false;
    }
});