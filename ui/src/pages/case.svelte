<script context="module">
    jQuery(document).ready(function(){
        jQuery('#case_quick_status').change(function(){
            post_request_api('/case/update-status', JSON.stringify({
                'status_id': jQuery('#case_quick_status').val(),
                'csrf_token': jQuery('#csrf_token').val()
            }))
            .done((data) => {
                if (notify_auto_api(data)) {
                    window.location.reload();
                }
            })
        });
    });
</script>
