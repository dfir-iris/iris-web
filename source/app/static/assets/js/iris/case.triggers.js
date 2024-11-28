document.addEventListener("DOMContentLoaded", () => {
    const table = document.getElementById("trigger_table");

    table.addEventListener("click", (event) => {
        if (event.target && event.target.classList.contains("view-response")) {
            const button = event.target;

            const responseData = button.getAttribute("data-response");
            const parsedData = JSON.parse(responseData);
            const jsonCrackEmbed = document.getElementById("jsoncrackEmbed");

            const modal = new bootstrap.Modal(document.getElementById("responseModal"));
            modal.show();
            //Check iframe is loaded and contentWindow is available
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
});




function closeModal() {
    const modal = bootstrap.Modal.getInstance(document.getElementById("responseModal"));
    modal.hide();
}