function objectToQueryString(obj) {
  return Object.keys(obj)
    .filter(key => obj[key] !== undefined && obj[key] !== null && obj[key] !== '')
    .map(key => encodeURIComponent(key) + '=' + encodeURIComponent(obj[key]))
    .join('&');
}

function escalateAlertModal(alert_id) {
    const escalateButton = document.getElementById("escalateButton");
    escalateButton.setAttribute("data-alert-id", alert_id);
    $("#escalateModal").modal("show");
}

function escalateAlert(alert_id) {
    post_request_api(`/alerts/escalate/${alert_id}?cid=${get_caseid()}`)
        .then((data) => {
            if (data.status == 'success') {
                $("#escalateModal").modal("hide");
                notify_auto_api(data);
            } else {
                notify_auto_api(data);
            }
        });
}

async function fetchAlerts(page, per_page, filters_string = {}) {
  const response = get_raw_request_api(`/alerts/filter?cid=${get_caseid()}&page=${page}&per_page=${per_page}&${filters_string}`);
  return await response;
}

async function updateAlerts(page, per_page, filters = {}) {
  const filterString = objectToQueryString(filters);
  const data = await fetchAlerts(page, per_page, filterString);

  if (!notify_auto_api(data, true)) {
    return;
  }
  const alerts = data.data.alerts;

  // Clear the current alerts list
  const alertsContainer = document.querySelector('.alerts-container');
  alertsContainer.innerHTML = '';

  // Add the fetched alerts to the alerts container
  alerts.forEach((alert) => {
    const alertElement = document.createElement('div');
    alertElement.innerHTML = `
      <div class="card alert-card full-height">
        <div class="card-body">
          <div class="d-flex">
            <div class="avatar mt-2">
              <span class="avatar-title rounded-circle border border-white bg-dark"><i class="fa-solid fa-fire"></i></span>
            </div>
            <div class="flex-1 ml-3 pt-1">
              <h6 class="text-uppercase fw-bold mb-1">${alert.alert_title} <span class="text-warning pl-3">${alert.alert_type}</span></h6>
              <span class="text-muted">${alert.alert_description.substring(0, 150)}</span><br/>
              <div class="mt-2">
                
                <span title="Alert source event time"><b><i class="fa-regular fa-calendar-check"></i></b>
                <small class="text-muted ml-1">${alert.alert_source_event_time}</small></span>
                <span title="Alert severity"><b class="ml-4"><i class="fa-solid fa-bolt"></i></b>
                  <small class="text-muted ml-1">${alert.severity.severity_name}</small></span>
                <span title="Alert status"><b class="ml-4"><i class="fa-solid fa-filter"></i></b>
                  <small class="text-muted ml-1">${alert.status.status_name}</small></span>
                <span title="Alert source"><b class="ml-4"><i class="fa-solid fa-cloud-arrow-down"></i></b>
                  <small class="text-muted ml-1">${alert.source || 'Unspecified'}</small></span>
                <span title="Alert UUID"><small class="text-muted ml-1"><i>#${alert.alert_uuid}</i></small></span>
                <span title="Alert UUID"><small class="text-muted ml-1"><i>#${alert.alert_id}</i></small></span>
              </div>
            </div>
            <div class="float-right ml-2">
              <button type="button" class="btn btn-light btn-xs dropdown-toggle" data-toggle="dropdown" aria-expanded="false">
                <span class="btn-label">
                  <i class="fa fa-cog"></i>
                </span>
              </button>
              <div class="dropdown-menu" role="menu" x-placement="bottom-start" style="position: absolute; transform: translate3d(0px, 32px, 0px); top: 0px; left: 0px; will-change: transform;">
                <a href="#" class="dropdown-item" onclick="copy_object_link_md('alert', ${alert.alert_id});return false;"><small class="fa-brands fa-markdown mr-2"></small>Markdown Link</a>
                <div class="dropdown-divider"></div>
                <a href="#" class="dropdown-item text-danger" onclick="remove_alert_from_case(${alert.alert_id}, 1);"><small class="fa fa-link-slash mr-2"></small>Unlink alert</a>
              </div>
            </div>
          </div>
        </div>
         <div class="alert-actions mr-2">
          <button type="button" class="btn btn-alert-primary btn-sm ml-2" onclick="escalateAlertModal(${alert.alert_id});">Escalate to new case</button>
          <button type="button" class="btn btn-alert-primary btn-sm ml-2" onclick="mergeAlert(${alert.alert_id});">Merge into case</button>
          <button type="button" class="btn btn-alert-success btn-sm ml-2" onclick="resolveAlert(${alert.alert_id});">Resolve</button>
          <button type="button" class="btn btn-alert-danger btn-sm ml-2" onclick="closeAlert(${alert.alert_id});">Close</button>
        </div>
      </div>    
    `;
    alertsContainer.appendChild(alertElement);
  });

  // Update the pagination links
  const currentPage = page;
  const totalPages = Math.ceil(data.data.total / per_page);
  createPagination(currentPage, totalPages, per_page, 'updateAlerts', '.pagination-container');

  // Update the URL with the filter parameters
  const queryParams = new URLSearchParams(window.location.search);
  queryParams.set('page', page);
  queryParams.set('per_page', per_page);

  for (const key in filters) {
    if (filters.hasOwnProperty(key)) {
      if (filters[key] === '') {
        queryParams.delete(key);
      } else {
        queryParams.set(key, filters[key]);
      }
    }
  }

  history.replaceState(null, null, `?${queryParams.toString()}`);

}

document.querySelector('#alertsPerPage').addEventListener('change', (e) => {
  const per_page = parseInt(e.target.value, 10);
  updateAlerts(1, per_page); // Update the alerts list with the new 'per_page' value and reset to the first page
});

document.querySelector('#alertFilterForm').addEventListener('submit', (e) => {
  e.preventDefault();

  // Get the filter values from the form
  const formData = new FormData(e.target);
  const filters = Object.fromEntries(formData.entries());

  // Update the alerts list with the new filters and reset to the first page
  updateAlerts(1, document.querySelector('#alertsPerPage').value, filters);
});

document.getElementById('resetFilters').addEventListener('click', function () {
    const form = document.getElementById('alertFilterForm');

    // Reset all input fields
    form.querySelectorAll('input, select').forEach((element) => {
        if (element.type === 'checkbox') {
            element.checked = false;
        } else {
            element.value = '';
        }
    });

    // Trigger the form submit event to fetch alerts with the updated filters
    form.dispatchEvent(new Event('submit'));
});

document.getElementById("escalateButton").addEventListener("click", () => {

    const alertId = document.getElementById("escalateButton").getAttribute("data-alert-id");

    escalateAlert(alertId);

});

// Load the filter parameters from the URL
const queryParams = new URLSearchParams(window.location.search);
const page = parseInt(queryParams.get('page') || '1', 10);
const per_page = parseInt(queryParams.get('per_page') || '10', 10);
updateAlerts(page, per_page, {});