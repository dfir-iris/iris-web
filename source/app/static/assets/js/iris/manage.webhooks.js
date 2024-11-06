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

document.getElementById('copyModalContent').addEventListener('click', function() {
    // Select the elements containing the modal data
    const name = document.getElementById('webhookName').innerText;
    const description = document.getElementById('webhookDescription').innerText;

    // Format the content to be copied
    const modalContent = `Name: ${name}\nDescription: ${description}`;

    // Check if the browser supports navigator.clipboard
    if (navigator.clipboard && window.isSecureContext) {
        // Use Clipboard API for modern browsers
        navigator.clipboard.writeText(modalContent).then(() => {
            notify_success('Content copied to clipboard!');
        }).catch(err => {
            console.error('Failed to copy content: ', err);
            notify_success('Failed to copy content.');
        });
    } else {
        // Fallback method for older browsers
        const tempTextArea = document.createElement('textarea');
        tempTextArea.value = modalContent;
        document.body.appendChild(tempTextArea);
        tempTextArea.select();

        try {
            document.execCommand('copy');
            notify_success("content copied");
        } catch (err) {
            console.error('Failed to copy content: ', err);
            notify_error("failed to copy content");
        }

        document.body.removeChild(tempTextArea);
    }
});

