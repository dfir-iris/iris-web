function toggleJsonViewer(button) {
    const responseData = button.getAttribute('data-response');
    const parsedData = JSON.parse(responseData);
    const jsonCrackEmbed = document.getElementById("jsoncrackIframe");

    // Find the expandable div container
    const jsonViewerContainer = $('#jsonViewerContainer');

    // Slide down to show the div
    jsonViewerContainer.slideDown();

    // Check if iframe is loaded and contentWindow is available
    if (jsonCrackEmbed && jsonCrackEmbed.contentWindow) {
        // Define options for JSONCrack
        const options = {
            theme: "light", 
            direction: "DOWN", 
        };

        // Post message to jsonCrackEmbed iframe
        jsonCrackEmbed.contentWindow.postMessage({ json: JSON.stringify(parsedData), options }, "*");
    } else {
        console.error("jsonCrackEmbed iframe is not available or not loaded.");
    }

    // Attach event to the close button to hide the div
    $('#jsonViewerContainer').find('.btn[data-dismiss="collapse-frame"]').on('click', function () {
        jsonViewerContainer.slideUp(); // Hides the div with a slide-up effect
    });
}
