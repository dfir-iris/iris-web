function objectToQueryString(obj) {
  return Object.keys(obj)
    .filter(key => obj[key] !== undefined && obj[key] !== null && obj[key] !== '')
    .map(key => encodeURIComponent(key) + '=' + encodeURIComponent(obj[key]))
    .join('&');
}

async function fetchAlert(alertId) {
    const response = get_raw_request_api(`/alerts/${alertId}?cid=${get_caseid()}`);
    return await response;
}


async function escalateAlertModal(alert_id) {
    const escalateButton = $("#escalateButton");
    escalateButton.attr("data-alert-id", alert_id);

    const alertDataReq = await fetchAlert(alert_id);
    const ioCsList = $("#ioCsList");
    const assetsList = $("#assetsList");

    $("#modalAlertId").val(alert_id);
    $("#modalAlertTitle").val(alertDataReq.data.alert_title);

    // Clear the lists
    ioCsList.html("");
    assetsList.html("");

    if (!notify_auto_api(alertDataReq, true)) {
        return;
    }

    alertData = alertDataReq.data;

    if (alertData.alert_iocs.length !== 0) {
        alertData.alert_iocs.forEach((ioc) => {
            const label = $('<label></label>').addClass('d-block');
            const input = $('<input>').attr({
                type: 'checkbox',
                name: 'ioc',
                value: ioc.uuid,
                checked: true,
            });
            label.append(input);
            label.append(` ${ioc.name}`);
            ioCsList.append(label);
        });

        $("#toggle-iocs").on("click", function () {
            let allChecked = true;
            $("#ioCsList input[type='checkbox']").each(function () {
                if (!$(this).prop("checked")) {
                    allChecked = false;
                }
                $(this).prop("checked", !$(this).prop("checked"));
            });

            if (allChecked) {
                $(this).text("Select All");
            } else {
                $(this).text("Deselect All");
            }
        });
        $("#ioc-container").show();
    } else {
        $("#ioc-container").show();
    }

    if (alertData.alert_assets.length !== 0) {
        alertData.alert_assets.forEach((asset) => {
            const label = $('<label></label>').addClass('d-block');
            const input = $('<input>').attr({
                type: 'checkbox',
                name: 'asset',
                value: asset.uuid,
                checked: true,
            });
            label.append(input);
            label.append(` ${asset.name}`);
            assetsList.append(label);
        });

        $("#toggle-assets").on("click", function () {
            let allChecked = true;
            $("#assetsList input[type='checkbox']").each(function () {
                if (!$(this).prop("checked")) {
                    allChecked = false;
                }
                $(this).prop("checked", !$(this).prop("checked"));
            });

            if (allChecked) {
                $(this).text("Select All");
            } else {
                $(this).text("Deselect All");
            }
        });
        $("#asset-container").show();
    } else {
        $("#asset-container").hide();
    }

    $("#escalateModal").modal("show");
}

function escalateAlert(alert_id) {
    post_request_api(`/alerts/escalate/${alert_id}`)
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

function alert_severity_to_color(severity) {
  switch (severity) {
    case 'Critical':
      return 'critical';
    case 'High':
      return 'danger';
    case 'Medium':
      return 'warning';
    case 'Low':
      return 'low';
    case 'Informational':
      return 'info';
    default:
      return 'muted';
  }
}

async function updateAlerts(page, per_page, filters = {}) {
  const filterString = objectToQueryString(filters);
  const data = await fetchAlerts(page, per_page, filterString);

  if (!notify_auto_api(data, true)) {
    return;
  }
  const alerts = data.data.alerts;

  // Clear the current alerts list
  const alertsContainer = $('.alerts-container');
  alertsContainer.html('');

  // Add the fetched alerts to the alerts container
  alerts.forEach((alert) => {
    const alertElement = $('<div></div>');

    const colorSeverity = alert_severity_to_color(alert.severity.severity_name);

    alertElement.html(`
       <div class="card alert-card full-height">
        <div class="card-body">
          <div class="d-flex">
            <div class="avatar mt-2">
              <span class="avatar-title rounded-circle  bg-${colorSeverity}"><i class="fa-solid fa-fire"></i></span>
            </div>
            <div class="flex-1 ml-3 pt-1">
              <h6 class="text-uppercase fw-bold mb-1">${alert.alert_title} <span class="text-${colorSeverity} pl-3"></h6>
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
                <span title="Alert UUID" class="float-right"><small class="text-muted ml-1"><i>#${alert.alert_uuid}</i></small></span>
                <span title="Alert UUID" class="float-right"><small class="text-muted ml-1"><i>#${alert.alert_id} -</i></small></span>
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
    `);
    alertsContainer.append(alertElement);
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

$('#alertsPerPage').on('change', (e) => {
  const per_page = parseInt(e.target.value, 10);
  updateAlerts(1, per_page); // Update the alerts list with the new 'per_page' value and reset to the first page
});

$('#alertFilterForm').on('submit', (e) => {
  e.preventDefault();

  // Get the filter values from the form
  const formData = new FormData(e.target);
  const filters = Object.fromEntries(formData.entries());

  // Update the alerts list with the new filters and reset to the first page
  updateAlerts(1, $('#alertsPerPage').val(), filters);
});

$('#resetFilters').on('click', function () {
  const form = $('#alertFilterForm');

  // Reset all input fields
  form.find('input, select').each((_, element) => {
    if (element.type === 'checkbox') {
      $(element).prop('checked', false);
    } else {
      $(element).val('');
    }
  });

  // Trigger the form submit event to fetch alerts with the updated filters
  form.trigger('submit');
});

$("#escalateButton").on("click", () => {
  const alertId = $("#escalateButton").data("alert-id");
  escalateAlert(alertId);
});


function setFormValuesFromUrl() {
  const queryParams = new URLSearchParams(window.location.search);
  const form = $('#alertFilterForm');

  queryParams.forEach((value, key) => {
    const input = form.find(`[name="${key}"]`);
    if (input.length > 0) {
      if (input.prop('type') === 'checkbox') {
        input.prop('checked', value === 'true');
      } else {
        input.val(value);
      }
    }
  });

  const filters = form.serializeArray().reduce((acc, { name, value }) => {
    acc[name] = value;
    return acc;
  }, {});

   const page = parseInt(queryParams.get('page') || '1', 10);
   const per_page = parseInt(queryParams.get('per_page') || '10', 10);

  updateAlerts(page, per_page, filters);
}

$(document).ready(function () {
    setFormValuesFromUrl();
});