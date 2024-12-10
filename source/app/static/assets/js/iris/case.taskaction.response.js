function toggleJsonViewer(button) {
    const responseId = button.getAttribute('data-task');  // Get task ID from the button's data-task attribute
    console.log("Task ID in toggle:", typeof responseId);

    // Parse the response ID to integer
    let id = parseInt(responseId);
    if (isNaN(id)) {
        console.error("Invalid task ID:", responseId);
        return;  // Exit if the ID is invalid
    }

    // Make an API call to fetch the task's action response
    fetch(`/case/task/action_response/${id}`)
        .then(response => response.json())
        .then(data => {

            if (data.status && data.data) {
                // Assuming the response data contains the 'data' field with the task action response
                console.log(data.data.body);
                const responseData = data.data.body; // Get the action response data

                const jsonCrackEmbed = document.getElementById("jsoncrackIframe");
                console.log("Parsed data to be displayed in JSONCrack:", responseData);

                // Find the expandable div container
                const jsonViewerContainer = $('#jsonViewerContainer');

                // Slide down to show the div
                jsonViewerContainer.slideDown();
                console.log("here");

                // Check if iframe is loaded and contentWindow is available
                if (jsonCrackEmbed && jsonCrackEmbed.contentWindow) {
                    // Define options for JSONCrack
                    const options = {
                        theme: "light", 
                        direction: "DOWN", 
                    };

                    // Post message to jsonCrackEmbed iframe with the response data
                    jsonCrackEmbed.contentWindow.postMessage({ json: JSON.stringify(responseData), options }, "*");
                } else {
                    console.error("jsonCrackEmbed iframe is not available or not loaded.");
                }
            } else {
                console.error("Failed to fetch action response data:", data);
            }
        })
        .catch(error => {
            console.error("Error fetching task action response:", error);
        });

    // Attach event to the close button to hide the div
    $('#jsonViewerContainer').find('.btn[data-dismiss="collapse-frame"]').off('click').on('click', function () {
        jsonViewerContainer.slideUp(); // Hides the div with a slide-up effect
    });
}
