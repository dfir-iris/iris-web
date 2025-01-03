function toggleJsonViewer(button) {
    const responseId = button.getAttribute('data-task');
    console.log("Task ID in toggle:", typeof responseId);
    let id = parseInt(responseId);
    if (isNaN(id)) {
        console.error("Invalid task ID:", responseId);
        return;  
    }

    fetch(`/case/task/action_response/${id}`)
        .then(response => response.json())
        .then(data => {
            if (data.status && data.data) {
                console.log(data.data.body);
                const responseData = data.data.body;

                const jsonCrackEmbed = document.getElementById("jsoncrackIframe");
                console.log("Parsed data to be displayed in JSONCrack:", responseData);
                const jsonViewerContainer = $('#jsonViewerContainer');

                // Show the container
                jsonViewerContainer.slideDown();
                console.log("here");

                // Post data to the iframe
                if (jsonCrackEmbed && jsonCrackEmbed.contentWindow) {
                    const options = {
                        theme: "light", 
                        direction: "DOWN", 
                    };

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

    // Attach event handler for the close button
    $('#jsonViewerContainer .btn[data-dismiss="collapse-frame"]').off('click').on('click', function () {
        $('#jsonViewerContainer').slideUp(); // Hide the container
    });
}
