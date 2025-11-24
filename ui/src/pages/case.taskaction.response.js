function toggleJsonViewer(button) {
    const responseId = button.getAttribute('data-task');
    const id = parseInt(responseId, 10);
    if (isNaN(id)) {
        console.error('Invalid task response ID:', responseId);
        return;
    }

    fetch(`/case/task/action_response/${id}` + case_param())
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        })
        .then(payload => {
            if (!(payload.status && payload.data)) {
                console.error('Unexpected payload format', payload);
                return;
            }

            const body = payload.data.body ?? {};
            const jsonViewerContainer = $('#jsonViewerContainer');
            jsonViewerContainer.slideDown();

            const iframeEl = document.getElementById('jsoncrackIframe');
            /** @type {HTMLIFrameElement|null} */
            const iframe = iframeEl instanceof HTMLIFrameElement ? iframeEl : null;
            if (!iframe || !iframe.contentWindow) {
                console.error('jsoncrackIframe not ready');
                return;
            }
            const options = { theme: 'light', direction: 'DOWN' };
            try {
                iframe.contentWindow.postMessage({ json: JSON.stringify(body), options }, 'https://jsoncrack.com');
            } catch (e) {
                console.error('Failed to postMessage to iframe:', e);
            }
        })
        .catch(err => {
            console.error('Error fetching task action response:', err);
        });

    $('#jsonViewerContainer .btn[data-dismiss="collapse-frame"]').off('click').on('click', function () {
        $('#jsonViewerContainer').slideUp();
    });
}