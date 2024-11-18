$('#actions_triggers_table').dataTable({
    "data": dummyData,  // Use dummy data instead of AJAX
    "order": [[2, "desc"]],  // Sort by 'created_at' column in descending order
    "autoWidth": false,
    "columns": [
        { 'data': 'id' },  // Unique ID
        { 'data': 'action_name' },  // Name of the action
        { 'data': 'trigger_condition' },  // Condition for triggering
        { 'data': 'created_at' },  // Creation date
        { 'data': 'status' },  // Status (Active/Inactive)
        { 'data': 'user' }  // user status
    ],
    "columnDefs": [
        {
            "render": function (data, type, row) {
                data = sanitizeHTML(data);
                return '<a href="#" onclick="view_action_details(\'' + row['id'] + '\');">' + data + '</a>';
            },
            "targets": [1]
        },
        {
            "render": function (data, type, row) {
                data = sanitizeHTML(data);
                return '<span data-toggle="tooltip" title="Condition: ' + data + '">' + data + '</span>';
            },
            "targets": [2]
        },
        {
            "render": function (data, type, row) {
                const date = new Date(data);
                return date.toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                });
            },
            "targets": [3]
        },
        {
            "render": function (data, type, row) {
                if (data === true) {
                    return '<i class="fas fa-check-circle text-success"></i> Active';
                } else {
                    return '<i class="fas fa-times-circle text-danger"></i> Inactive';
                }
            },
            "targets": [4]
        },
        {
            "render": function (data, type, row) {
                if (data === false) {
                    return '<i class="fas fa-exclamation-triangle text-warning" data-toggle="tooltip" title="Please configure this action to activate."></i>';
                } else {
                    return '<i class="fas fa-cogs text-primary"></i> user';
                }
            },
            "targets": [5]
        }
    ],
    "initComplete": function () {
        $('[data-toggle="tooltip"]').tooltip();
    }
});
