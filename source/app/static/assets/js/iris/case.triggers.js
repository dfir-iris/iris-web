// Dummy data for triggers
var g_trigger_id = null;
const dummyTriggers = [
    {
        "id": 1,
        "case": 101,
        "trigger": 202,
        "body": {
            "status": "success",
            "message": "Action executed successfully",
            "details": {
                "step_1": "Initiated",
                "step_2": "Completed"
            }
        },
        "execution_time": "2024-11-13T14:30:00Z"
    },
    {
        "id": 2,
        "case": 103,
        "trigger": 202,
        "body": {
            "status": "success",
            "message": "Action executed successfully",
            "details": {
                "step_1": "Initiated",
                "step_2": "Completed"
            }
        },
        "execution_time": "2024-11-13T14:50:00Z"
    }
];

// Function to load dummy trigger data into the table
function get_triggers() {
    $('#trigger_table_wrapper').empty();
    show_loader();

    Table.clear();  // Clear existing rows
    Table.rows.add(dummyTriggers);  // Add dummy data
    Table.draw();  // Redraw the table

    hide_loader();
}

// Initialize DataTable with three columns for triggers
$(document).ready(function () {
    Table = $("#trigger_table").DataTable({
        dom: '<"container-fluid"<"row"<"col"l><"col"f>>>rt<"container-fluid"<"row"<"col"i><"col"p>>>',
        data: [],
        columns: [
            { data: "id", title: "ID" },
            { data: "case", title: "Case" },
            { data: "trigger", title: "Trigger" },
            {
                data: "body",
                title: "Response",
                render: function (data, type, row) {
                    if (type === 'display') {
                        return '<button class="btn btn-primary btn-sm view-response" data-body=\'' + JSON.stringify(data) + '\'>View Response</button>';
                    }
                    return data;
                }
            },
            { data: "execution_time", title: "Execution Time" }
        ],
        processing: true,
        ordering: true,
        pageLength: 10,
        responsive: true,
        order: [[0, 'asc']],
    });

    // Initial fetch of trigger data (dummy)
    get_triggers();

    // Event listener for 'View Response' button to open the modal with iframe
    $('#trigger_table').on('click', '.view-response', function () {
        const responseData = $(this).data('body');
        const iframeUrl = 'http://localhost:3000'; // Replace with the desired URL
    
        // Prepare data to send
        const dataToSend = {
            response: responseData
        };
    
        // Send fetch request to the server
        fetch('http://localhost:3000/api/receive-data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(dataToSend)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log('Success:', data);
    
            // Open the modal after successful data send
            $('#responseModal').modal('show');
            $('#modalIframe').attr('src', iframeUrl + '?data=' + encodeURIComponent(JSON.stringify(responseData)));
        })
        .catch((error) => {
            console.error('Error:', error);
            alert('Failed to send data to the server.');
        });
    });
    
});

function closeModal() {
    // Hide the modal
    document.getElementById('responseModal').style.display = 'none';
}

// Helper functions to show/hide loader
function show_loader() {
    $('#loading_msg').show();
    $('#card_main_load').hide();
}

function hide_loader() {
    $('#loading_msg').hide();
    $('#card_main_load').show();
}
