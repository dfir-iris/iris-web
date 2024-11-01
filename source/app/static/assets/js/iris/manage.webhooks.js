$('#webhooks_table').DataTable({
    "ajax": {
        "url": "/manage/attributes/list" + case_param(),
        "contentType": "application/json",
        "type": "GET",
        "data": function (d) {
            return d.status === 'success' ? JSON.stringify(d.data) : [];
        }
    },
    "order": [[0, "desc"]],
    "autoWidth": false,
    "columns": [
        {
            "data": "attribute_display_name"
        },
        {
            "data": "attribute_description"
        }
    ]
});

// Event listener for row clicks
$('#webhooks_table tbody').on('click', 'tr', function () {
    var table = $('#webhooks_table').DataTable();
    var data = table.row(this).data();

    // Populate modal with data
    $('#webhookName').text(data.attribute_display_name);
    $('#webhookDescription').text(data.attribute_description);

    // Show modal
    $('#webhookModal').modal('show');
});
