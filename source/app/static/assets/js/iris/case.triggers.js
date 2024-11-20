
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


function get_triggers() {
    $('#trigger_table_wrapper');
    show_loader();

    Table.clear();  
    Table.rows.add(dummyTriggers);  
    Table.draw();  

    hide_loader();
}


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


    get_triggers();


    $('#trigger_table').on('click', '.view-response', function () {
        const responseData = $(this).data('body');
        const jsonCrackEmbed = document.getElementById("jsoncrackEmbed");

        $('#responseModal').modal('show');


        const options = {
            theme: "light", 
            direction: "DOWN", 
        };
        jsonCrackEmbed.contentWindow.postMessage({ json: JSON.stringify(responseData), options }, "*");
    });
});


function closeModal() {
    $('#responseModal').modal('hide');
}


function show_loader() {
    $('#loading_msg').show();
    $('#card_main_load').hide();
}

function hide_loader() {
    $('#loading_msg').hide();
    $('#card_main_load').show();
}
