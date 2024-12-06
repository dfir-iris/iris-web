document.addEventListener("DOMContentLoaded", () => {
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
            const parsedData = JSON.parse(responseData);
            const jsonCrackEmbed = document.getElementById("jsoncrackEmbed");

            modal.show();

            // Check iframe is loaded and contentWindow is available
            if (jsonCrackEmbed && jsonCrackEmbed.contentWindow) {
                // Define options for jsonCrack
                const options = {
                    theme: "light", 
                    direction: "DOWN", 
                };

                // Post message to jsonCrackEmbed iframe
                jsonCrackEmbed.contentWindow.postMessage({ json: JSON.stringify(parsedData), options }, "*");
            } else {
                console.error("jsonCrackEmbed iframe is not available or not loaded.");
            }
        }
    });

    // Close modal when the close button is clicked
    if (closeButton) {
        closeButton.addEventListener("click", () => {
            modal.hide(); // Use the modal instance to close
        });
    }
});
