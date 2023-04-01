async function fetchAlerts(page, per_page) {
  const response = get_raw_request_api(`/alerts/filter?cid=${get_caseid()}&page=${page}&per_page=${per_page}`);
  return await response;
}

async function updateAlerts(page) {
  const per_page = 10;
  const data = await fetchAlerts(page, per_page);

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
      <div class="card full-height" style="border-radius: 15px;margin-bottom: 10px;">
        <div class="card-body">
          <div class="d-flex">
            <div class="avatar mt-2">
              <span class="avatar-title rounded-circle border border-white bg-dark"><i class="fa-solid fa-link"></i></span>
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
                <a href="#" class="dropdown-item text-danger" onclick="remove_alert_from_case(${alert.alert_id}, {{ session['current_case'].case_id }});"><small class="fa fa-link-slash mr-2"></small>Unlink alert</a>
              </div>
            </div>
          </div>
        </div>
      </div>    
    `;
    alertsContainer.appendChild(alertElement);
  });

  // Update the pagination links
  const paginationContainer = document.querySelector('.pagination-container');
  paginationContainer.innerHTML = '';

  for (let i = 1; i <= Math.ceil(data.data.total / per_page); i++) {
    const pageLink = document.createElement('a');
    pageLink.href = `javascript:updateAlerts(${i})`;
    pageLink.textContent = i;
    pageLink.className = 'page-link';

    const pageItem = document.createElement('li');
    pageItem.className = 'page-item';
    if (i === page) {
      pageItem.className += ' active';
    }
    pageItem.appendChild(pageLink);
    paginationContainer.appendChild(pageItem);
  }
}

updateAlerts(1); // Initial call to load the first page