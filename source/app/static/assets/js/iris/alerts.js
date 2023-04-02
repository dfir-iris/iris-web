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

function generateDefinitionList(obj) {
  let html = "";
  for (const key in obj) {
    const value = obj[key];
    html += `<dt>${key}:</dt>`;
    if (typeof value === "object" && value !== null) {
      html += `<dd><dl>${generateDefinitionList(value)}</dl></dd>`;
    } else {
      html += `<dd>${value}</dd>`;
    }
  }
  return html;
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
            <div class="avatar mt-2 cursor-pointer">
                <span class="avatar-title alert-m-title rounded-circle bg-${colorSeverity}" data-toggle="collapse" data-target="#additionalDetails-${alert.alert_id}"><i class="fa-solid fa-fire"></i></span>
            </div>
            <div class="flex-1 ml-3 pt-1">
                <h6 class="text-uppercase fw-bold mb-1 alert-m-title alert-m-title-${colorSeverity}" data-toggle="collapse" data-target="#additionalDetails-${alert.alert_id}">
                  ${alert.alert_title}
                  <span class="text-${colorSeverity} pl-3"></span>
                </h6>
                <div class="d-flex mb-3">
                    <span title="Alert IDs" class=""><small class="text-muted"><i>#${alert.alert_id} - ${alert.alert_uuid}</i></small></span>
                </div>
              <span class="">${alert.alert_description}</span><br/>
              <div id="additionalDetails-${alert.alert_id}" class="collapse mt-4">
                <div class="card p-3 mt-2">
                    <div class="card-body">
                    <h3 class="title mb-3"><strong>General info</strong></h3>  
                      <div class="row">
                        ${alert.alert_source ? `<div class="col-md-3"><b>Source:</b></div>
                        <div class="col-md-9">${alert.alert_source}</div>
                      </div>`: ''}
                      ${alert.alert_source_link ? `<div class="row mt-2">
                        <div class="col-md-3"><b>Source Link:</b></div>
                        <div class="col-md-9"><a href="${alert.alert_source_link}">${alert.alert_source_link}</a></div>
                      </div>`: ''}
                      ${alert.alert_source_ref ? `<div class="row mt-2">
                        <div class="col-md-3"><b>Source Reference:</b></div>
                        <div class="col-md-9">${alert.alert_source_ref}</div>
                      </div>`: ''}
                      ${alert.alert_source_event_time ? `<div class="row mt-2">
                        <div class="col-md-3"><b>Source Event Time:</b></div>
                        <div class="col-md-9">${alert.alert_source_event_time}</div>
                      </div>`: ''}
                      ${alert.alert_creation_time ? `<div class="row mt-2">
                        <div class="col-md-3"><b>IRIS Creation Time:</b></div>
                        <div class="col-md-9">${alert.alert_creation_time}</div>
                      </div>`: ''}
                    
                    <!-- Alert Context section -->
                    ${
                      alert.alert_context && Object.keys(alert.alert_context).length > 0
                        ? `<div class="separator-solid"></div><h3 class="title mt-3 mb-3"><strong>Context</strong></h3>
                           <dl class="row">
                             ${Object.entries(alert.alert_context)
                               .map(
                                 ([key, value]) =>
                                   `<dt class="col-sm-3">${key}</dt>
                                    <dd class="col-sm-9">${value}</dd>`
                               )
                               .join('')}
                           </dl>`
                        : ''
                    }
                
                    <!-- Alert IOCs section -->
                    ${
                      alert.alert_iocs && alert.alert_iocs.length > 0
                        ? `<div class="separator-solid"></div><h3 class="title mb-3"><strong>IOCs</strong></h3>
                           <div class="table-responsive">
                             <table class="table table-sm table-striped">
                               <thead>
                                 <tr>
                                   <th>Value</th>
                                   <th>Description</th>
                                   <th>Type</th>
                                   <th>TLP</th>
                                   <th>Tags</th>
                                   <th>Enrichment</th>
                                 </tr>
                               </thead>
                               <tbody>
                                 ${alert.alert_iocs
                                   .map(
                                     (ioc) => `
                                     <tr>
                                       <td>${ioc.ioc_value}</td>
                                       <td>${ioc.ioc_description}</td>
                                       <td>${ioc.ioc_type ? ioc.ioc_type : '-'}</td>
                                       <td>${ioc.ioc_tags ? ioc.ioc_tlp : '-'}</td>
                                       <td>${ioc.ioc_tags ? ioc.ioc_tags.map((tag) => `<span class="badge badge-pill badge-light ml-1"><i class="fa fa-tag mr-1"></i>${tag}</span>`).join(''): ''}</td>
                                       <td>${ioc.ioc_enrichment ? `<button type="button" class="btn btn-sm btn-outline-dark" data-toggle="modal" data-target="#enrichmentModal" onclick="showEnrichment(${JSON.stringify(ioc.ioc_enrichment).replace(/"/g, '&quot;')})">
                                          View Enrichment
                                        </button>` : ''}
                                        </td>
                                     </tr>`
                                   )
                                   .join('')}
                               </tbody>
                             </table>
                           </div>`
                        : ''
                    }
                    
                    <!-- Alert assets section -->
                    ${
                      alert.alert_assets && alert.alert_assets.length > 0
                        ? `<div class="separator-solid"></div><h3 class="title mb-3"><strong>Assets</strong></h3>
                           <div class="table-responsive">
                             <table class="table table-sm table-striped">
                               <thead>
                                 <tr>
                                   <th>Name</th>
                                   <th>Description</th>
                                   <th>Type</th>
                                   <th>Domain</th>
                                   <th>IP</th>
                                   <th>Tags</th>
                                   <th>Enrichment</th>
                                 </tr>
                               </thead>
                               <tbody>
                                 ${alert.alert_assets
                                   .map(
                                     (asset) => `
                                     <tr>
                                       <td>${asset.asset_name ? asset.asset_name : '-'}</td>
                                       <td>${asset.asset_name ? asset.asset_description : '-'}</td>
                                       <td>${asset.asset_type ? asset.asset_type : '-'}</td>
                                       <td>${asset.asset_domain ? asset.asset_domain : '-'}</td>
                                       <td>${asset.asset_ip ? asset.asset_ip : '-'}</td>
                                       <td>${asset.asset_tags ? asset.asset_tags.map((tag) => `<span class="badge badge-pill badge-light ml-1"><i class="fa fa-tag mr-1"></i>${tag}</span>`).join(''): ''}</td>
                                       <td>${asset.asset_enrichment ? `<button type="button" class="btn btn-sm btn-outline-dark" data-toggle="modal" data-target="#enrichmentModal" onclick="showEnrichment(${JSON.stringify(asset.asset_enrichment).replace(/"/g, '&quot;')})">
                                          View Enrichment
                                        </button>` : ''}
                                        </td>
                                     </tr>`
                                   )
                                   .join('')}
                               </tbody>
                             </table>
                           </div>`
                        : ''
                    }
                    
                    ${
                      alert.alert_source_content
                        ? `<div class="separator-solid"></div><h3 class="title mt-3 mb-3"><strong>Raw Alert</strong></h3>
                           <button class="btn btn-sm btn-outline-dark" type="button" data-toggle="collapse" data-target="#rawAlert-${alert.alert_id}" aria-expanded="false" aria-controls="rawAlert-${alert.alert_id}">Toggle Raw Alert</button>
                           <div class="collapse mt-3" id="rawAlert-${alert.alert_id}">
                             <pre class="pre-scrollable">${JSON.stringify(alert.alert_source_content, null, 2)}</pre>
                           </div>`
                        : ""
                    }
                    
                    </div>
                  </div>
              </div>
              <div class="mt-4">
                
                <span title="Alert source event time"><b><i class="fa-regular fa-calendar-check"></i></b>
                <small class="text-muted ml-1">${alert.alert_source_event_time}</small></span>
                <span title="Alert severity"><b class="ml-3"><i class="fa-solid fa-bolt"></i></b>
                  <small class="text-muted ml-1">${alert.severity.severity_name}</small></span>
                <span title="Alert status"><b class="ml-3"><i class="fa-solid fa-filter"></i></b>
                  <small class="text-muted ml-1">${alert.status.status_name}</small></span>
                <span title="Alert source"><b class="ml-3"><i class="fa-solid fa-cloud-arrow-down"></i></b>
                  <small class="text-muted ml-1">${alert.alert_source || 'Unspecified'}</small></span>
                <span title="Alert client"><b class="ml-3"><i class="fa-regular fa-circle-user"></i></b>
                  <small class="text-muted ml-1 mr-4">${alert.customer.customer_name || 'Unspecified'}</small></span>
                ${alert.alert_tags ? alert.alert_tags.split(',').map((tag) => `<span class="badge badge-pill badge-light ml-1"><i class="fa fa-tag mr-1"></i>${tag}</span>`).join(''): ''}
              </div>
            </div>
            
            <div class="float-right ml-2">
              <button class="btn bg-transparent pull-right" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                  <span aria-hidden="true"><i class="fas fa-ellipsis-v"></i></span>
              </button>
              <div class="dropdown-menu" role="menu" x-placement="bottom-start" style="position: absolute; transform: translate3d(0px, 32px, 0px); top: 0px; left: 0px; will-change: transform;">
                <a href="#" class="dropdown-item" onclick="copy_object_link_md('alert', ${alert.alert_id});return false;"><small class="fa-brands fa-markdown mr-2"></small>Markdown Link</a>
                <div class="dropdown-divider"></div>
                <a href="#" class="dropdown-item text-danger" onclick="delete_alert(${alert.alert_id});"><small class="fa fa-trash mr-2"></small>Delete alert</a>
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

function showEnrichment(enrichment) {
  const enrichmentDataElement = document.getElementById('enrichmentData');
  enrichmentDataElement.innerHTML = generateDefinitionList(enrichment);
}

function delete_alert(alert_id) {
    post_request_api('/alerts/delete/'+alert_id)
    .then(function (data) {
        if (notify_auto_api(data)) {
            updateAlerts();
        }
    });
}

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

function fetchSelectOptions() {
    const selectElement = $('#alertStatusFilter');
    get_request_api('/manage/alert-status/list')
        .then(function (data) {
            if (!notify_auto_api(data, true)) {
                return;
            }
            selectElement.empty();
            data.data.forEach(function (item) {
                selectElement.append($('<option>', {
                    value: item.status_id,
                    text: item.status_name
                }));
            });
        });
}

$(document).ready(function () {
    setFormValuesFromUrl();
    fetchSelectOptions();
});