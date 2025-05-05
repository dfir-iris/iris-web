document.addEventListener("DOMContentLoaded", () => {
    loadTableData();
    const table = document.getElementById("trigger_table");
    const responseModal = document.getElementById("responseModal");
    const closeButton = responseModal.querySelector('[data-dismiss="hide-frame"]');
    
    // Initialize the modal instance
    const modal = new bootstrap.Modal(responseModal);
 
    // Show modal on "View Response" button click
    table.addEventListener("click", (event) => {
        if (event.target && event.target.classList.contains("view-response")) {
            const button = event.target;
            const responseData = button.getAttribute("data-response");
 
            // Check if responseData is valid JSON
            let parsedData;
            try {
                parsedData = JSON.parse(responseData);
            } catch (e) {
                console.error("Invalid JSON in response data:", e);
                return; // Stop if the data is not valid JSON
            }
 
            const jsonCrackEmbed = document.getElementById("jsoncrackEmbed");
 
            modal.show();

            if (jsonCrackEmbed && jsonCrackEmbed.contentWindow) {

                const options = {
                    theme: "light", 
                    direction: "DOWN", 
                };

                jsonCrackEmbed.contentWindow.postMessage({ json: JSON.stringify(parsedData), options }, "*");
            } else {
                console.error("jsonCrackEmbed iframe is not available or not loaded.");
            }
        }
    });

    if (closeButton) {
        closeButton.addEventListener("click", () => {
            modal.hide(); 
        });
    }});
 
    function loadTableData() {
        if (typeof caseId === "undefined") {
            console.error("Case ID is not defined.");
            return;
        }
    
        $("#trigger_table").dataTable({
            ajax: {
                url: `/case/triggers-list/${caseId}`, // Include caseId in the URL
                contentType: "application/json",
                type: "GET",
                dataSrc: "data",
            },
            order: [[0, "desc"]],
            autoWidth: false,
            columns: [
                { data: "id" },
                // { data: "trigger" },
                // { data: "case" },
                {
                    data: "body",
                    render: function (data, type, row) {
                        const task = row.id;
                        return `
                            <button type="button" class="btn btn-primary btn-sm view-response"
                                data-task='${task}'
                                data-response='${data}' >
                                View Response
                            </button>
                        `;
                    },
                },
                { data: "created_at" },
                { data: "updated_at" },
            ],
            error: function (xhr, error, code) {
                console.error("DataTables AJAX error:", xhr.responseText);
            },
        });
    
        setInterval(() => {
            $("#trigger_table").DataTable().ajax.reload(null, false);
        }, 3000);
    }
    