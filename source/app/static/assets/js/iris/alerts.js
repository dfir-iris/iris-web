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

const selectsConfig = {
    alertStatusFilter: {
        url: '/manage/alert-status/list',
        id: 'status_id',
        name: 'status_name',
    },
    alertSeverityFilter: {
        url: '/manage/severities/list',
        id: 'severity_id',
        name: 'severity_name'
    },
    alertClassificationFilter: {
        url: '/manage/case-classifications/list',
        id: 'id',
        name: 'name_expanded',
    },
    alertCustomerFilter: {
        url: '/manage/customers/list',
        id: 'customer_id',
        name: 'customer_name'
    },
    alertOwnerFilter: {
        url: '/manage/users/list',
        id: 'user_id',
        name: 'user_name'
    }
};

let alertStatusList = {};

function getAlertStatusList() {
    get_request_api('/manage/alert-status/list')
        .then((data) => {
            if (!notify_auto_api(data, true)) {
                return;
            }
            alertStatusList = data.data;
        });
}

function getAlertStatusId(statusName) {
    const status = alertStatusList.find((status) => status.status_name === statusName);
    return status ? status.status_id : undefined;
}

async function mergeAlertModal(alert_id, merge = false) {
    const escalateButton = $("#escalateOrMergeButton");
    escalateButton.attr("data-alert-id", alert_id);
    escalateButton.attr("data-merge", merge);

    const alertDataReq = await fetchAlert(alert_id);
    const ioCsList = $("#ioCsList");
    const assetsList = $("#assetsList");

    $("#modalAlertId").val(alert_id);
    $("#modalAlertTitle").val(alertDataReq.data.alert_title);

    if (merge) {
        $('#escalateModalLabel').text('Merge Alert');
        $('#escalateModalExplanation').text('This alert will be merged into the case. Select the IOCs and Assets to merge into the case.');
        $("#escalateOrMergeButton").text('Merge Alert')
        $('#mergeAlertCaseSelectSection').show();
        var options = {
                ajax: {
                url: '/context/search-cases'+ case_param(),
                type: 'GET',
                dataType: 'json'
            },
            locale: {
                    emptyTitle: 'Select and Begin Typing',
                    statusInitialized: '',
            },
            preprocessData: function (data) {
                return context_data_parser(data);
            },
            preserveSelected: false
        };
        await get_request_api('/context/get-cases/100')
            .done((data) => {
                mergeAlertCasesSelectOption(data);
                $('#mergeAlertCaseSelect').ajaxSelectPicker(options);
            });

    } else {
        $('#escalateModalLabel').text('Escalate Alert');
        $('#escalateModalExplanation').text('This alert will be escalated into a new case. Select the IOCs and Assets to escalate into the case.');
        $('#mergeAlertCaseSelectSection').hide();
    }

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
                value: ioc.ioc_name,
                id: ioc.ioc_uuid,
                checked: true,
            });
            label.append(input);
            label.append(` ${ioc.ioc_value}`);
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
                value: asset.asset_name,
                id: asset.asset_uuid,
                checked: true,
            });
            label.append(input);
            label.append(` ${asset.asset_name}`);
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
    if (merge) {
        $('#mergeAlertCaseSelect').selectpicker('refresh');
        $('#mergeAlertCaseSelect').selectpicker('val', get_caseid());
    }
}

function mergeAlertCasesSelectOption(data) {
    if(notify_auto_api(data, true)) {
        $('#mergeAlertCaseSelect').empty();

        $('#mergeAlertCaseSelect').append('<optgroup label="Opened" id="switchMergeAlertCasesOpen"></optgroup>');
        $('#mergeAlertCaseSelect').append('<optgroup label="Closed" id="switchMergeAlertCasesClose"></optgroup>');
        ocs = data.data;
        ret_data = [];
        for (index in ocs) {
            case_name = sanitizeHTML(ocs[index].name);
            cs_name = sanitizeHTML(ocs[index].customer_name);
            ret_data.push({
                        'value': ocs[index].case_id,
                        'text': `${case_name} (${cs_name}) ${ocs[index].access}`
                    });
            if (ocs[index].close_date != null) {
                $('#switchMergeAlertCasesClose').append(`<option value="${ocs[index].case_id}">${case_name} (${cs_name}) ${ocs[index].access}</option>`);
            } else {
                $('#switchMergeAlertCasesOpen').append(`<option value="${ocs[index].case_id}">${case_name} (${cs_name}) ${ocs[index].access}</option>`)
            }
        }

        return ret_data;
    }
}


function escalateOrMergeAlert(alert_id, merge = false) {

    const selectedIOCs = $('#ioCsList input[type="checkbox"]:checked').map((_, checkbox) => {
        return $(checkbox).attr('id');
    }).get();

    const selectedAssets = $('#assetsList input[type="checkbox"]:checked').map((_, checkbox) => {
        return $(checkbox).attr('id');
    }).get();

    const note = $('#note').val();
    const importAsEvent = $('#importAsEvent').is(':checked');

    const requestBody = {
        iocs_import_list: selectedIOCs,
        assets_import_list: selectedAssets,
        note: note,
        import_as_event: importAsEvent,
        csrf_token: $("#csrf_token").val()
    };

    if (merge) {
        requestBody.target_case_id = $('#mergeAlertCaseSelect').val();
    }

    post_request_api(`/alerts/${merge ? 'merge': 'escalate'}/${alert_id}`, JSON.stringify(requestBody))
        .then((data) => {
            if (data.status == 'success') {
                $("#escalateModal").modal("hide");
                notify_auto_api(data);
            } else {
                notify_auto_api(data);
            }
        });
}

async function fetchAlerts(page, per_page, filters_string = {}, sort_order= 'desc') {

    const response = get_raw_request_api(`/alerts/filter?cid=${get_caseid()}&page=${page}&per_page=${per_page}
  &sort=${sort_order}&${filters_string}`);

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

async function updateAlerts(page, per_page, filters = {}, sort_order = 'desc'){
  const filterString = objectToQueryString(filters);
  const data = await fetchAlerts(page, per_page, filterString, sort_order);

  if (!notify_auto_api(data, true)) {
    return;
  }
  const alerts = data.data.alerts;

  // Clear the current alerts list
  const alertsContainer = $('.alerts-container');
  alertsContainer.html('');

  if (alerts.length === 0) {
    // Display "No results" message when there are no alerts
    alertsContainer.append('<div class="ml-auto mr-auto">No results</div>');
  } else {

      // Add the fetched alerts to the alerts container
      alerts.forEach((alert) => {
          const alertElement = $('<div></div>');

          const colorSeverity = alert_severity_to_color(alert.severity.severity_name);

          alertElement.html(`
           <div class="card alert-card full-height alert-card-selectable" id="alertCard-${alert.alert_id}">
            <div class="card-body" >
              <div class="d-flex">
                <div class="avatar-group mt-3 ${alert.owner ? '': 'ml-2 mr-2' }">
                    <div class="avatar-tickbox-wrapper">
                       <div class="avatar-wrapper">
                            <div class="avatar cursor-pointer">
                                <span class="avatar-title alert-m-title rounded-circle bg-${colorSeverity}" data-toggle="collapse" data-target="#additionalDetails-${alert.alert_id}"><i class="fa-solid fa-fire"></i></span>
                            </div>
                            ${alert.owner ? get_avatar_initials(alert.owner.user_name, true, `changeAlertOwner(${alert.alert_id})`) : ''}
                            <div class="envelope-icon">
                                ${ alert.status ? `<span class="badge badge-pill badge-light">${alert.status.status_name}</span>`: ''} 
                            </div>
                        </div>
                    <div class="tickbox" style="display:none;">
                        <input type="checkbox" class="alert-selection-checkbox" data-alert-id="${alert.alert_id}" />
                     </div>
                    </div>
                </div>
                
                <div class="flex-1 ml-4 pt-1">
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
                          </div>` : ''}
                          ${alert.alert_source_link ? `<div class="row mt-2">
                            <div class="col-md-3"><b>Source Link:</b></div>
                            <div class="col-md-9"><a href="${alert.alert_source_link}">${alert.alert_source_link}</a></div>
                          </div>` : ''}
                          ${alert.alert_source_ref ? `<div class="row mt-2">
                            <div class="col-md-3"><b>Source Reference:</b></div>
                            <div class="col-md-9">${alert.alert_source_ref}</div>
                          </div>` : ''}
                          ${alert.alert_source_event_time ? `<div class="row mt-2">
                            <div class="col-md-3"><b>Source Event Time:</b></div>
                            <div class="col-md-9">${alert.alert_source_event_time}</div>
                          </div>` : ''}
                          ${alert.alert_creation_time ? `<div class="row mt-2">
                            <div class="col-md-3"><b>IRIS Creation Time:</b></div>
                            <div class="col-md-9">${alert.alert_creation_time}</div>
                          </div>` : ''}
                        
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
                                                       <td>${ioc.ioc_tags ? ioc.ioc_tags.map((tag) => `<span class="badge badge-pill badge-light ml-1"><i class="fa fa-tag mr-1"></i>${tag}</span>`).join('') : ''}</td>
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
                                           <td>${asset.asset_tags ? asset.asset_tags.map((tag) => `<span class="badge badge-pill badge-light ml-1"><i class="fa fa-tag mr-1"></i>${tag}</span>`).join('') : ''}</td>
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
                    <span title="Alert source"><b class="ml-3"><i class="fa-solid fa-cloud-arrow-down"></i></b>
                      <small class="text-muted ml-1">${alert.alert_source || 'Unspecified'}</small></span>
                    <span title="Alert client"><b class="ml-3"><i class="fa-regular fa-circle-user"></i></b>
                      <small class="text-muted ml-1 mr-2">${alert.customer.customer_name || 'Unspecified'}</small></span>
                    ${alert.classification.name_expanded ? `<span class="badge badge-pill badge-light" title="Classification"><i class="fa-solid fa-shield-virus mr-1"></i>${alert.classification.name_expanded}</span>`: ''}
                    ${alert.alert_tags ? alert.alert_tags.split(',').map((tag) => `<span class="badge badge-pill badge-light ml-1"><i class="fa fa-tag mr-1"></i>${tag}</span>`).join('') : ''}
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
                    <button type="button" class="btn btn-alert-primary btn-sm ml-2" onclick="mergeAlertModal(${alert.alert_id}, false);">Merge</button>
                    
                    <div class="dropdown ml-2 d-inline-block">
                        <button type="button" class="btn btn-alert-primary btn-sm dropdown-toggle" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                            Assign
                        </button>
                        <div class="dropdown-menu">
                            <a class="dropdown-item" href="#" onclick="updateAlert(${alert.alert_id}, {alert_owner_id: userWhoami.user_id}, true);">Assign to me</a>
                            <a class="dropdown-item" href="#" onclick="changeAlertOwner(${alert.alert_id});">Assign</a>
                        </div>
                    </div>
                    
                    <div class="dropdown ml-2 d-inline-block">
                        <button type="button" class="btn btn-alert-primary btn-sm dropdown-toggle" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                            Set status
                        </button>
                        <div class="dropdown-menu">
                            <a class="dropdown-item" href="#" onclick="changeStatusAlert(${alert.alert_id}, 'New');">New</a>
                            <a class="dropdown-item" href="#" onclick="changeStatusAlert(${alert.alert_id}, 'In progress');">In progress</a>
                            <a class="dropdown-item" href="#" onclick="changeStatusAlert(${alert.alert_id}, 'Pending');">Pending</a>
                            <a class="dropdown-item" href="#" onclick="changeStatusAlert(${alert.alert_id}, 'Closed');">Closed</a>
                            <a class="dropdown-item" href="#" onclick="changeStatusAlert(${alert.alert_id}, 'Merged');">Merged</a>
                        </div>
                    </div>
                    
                    <button type="button" class="btn btn-alert-danger btn-sm ml-2" onclick="closeAlert(${alert.alert_id});">Close</button>
                </div>
          </div>    
        `);
          alertsContainer.append(alertElement);
      });
  }

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

  queryParams.set('sort', sort_order);

  history.replaceState(null, null, `?${queryParams.toString()}`);

  $('#alertsInfoFilter').text(`${data.data.total} Alert${ data.data.total > 1 ? 's' : ''} ${ filterString ? '(filtered)' : '' }`);

}

$('#alertsPerPage').on('change', (e) => {
  const per_page = parseInt(e.target.value, 10);
  updateAlerts(1, per_page, undefined, sortOrder); // Update the alerts list with the new 'per_page' value and reset to the first page
});

let sortOrder = 'desc';

$('#orderAlertsBtn').on('click', function () {
  sortOrder = sortOrder === 'desc' ? 'asc' : 'desc';
  const iconClass = sortOrder === 'desc' ? 'fas fa-arrow-up-short-wide' : 'fas fa-arrow-up-wide-short';

  $('#orderAlertsBtn i').attr('class', iconClass);
  updateAlerts(1, 10, {}, sortOrder);
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

$("#escalateOrMergeButton").on("click", () => {
  const alertId = $("#escalateOrMergeButton").data("alert-id");
  const merge = $("#escalateOrMergeButton").data("merge");

  escalateOrMergeAlert(alertId, merge);
});

function showEnrichment(enrichment) {
  const enrichmentDataElement = document.getElementById('enrichmentData');
  enrichmentDataElement.innerHTML = generateDefinitionList(enrichment);
}

function delete_alert(alert_id) {
    post_request_api('/alerts/delete/'+alert_id)
    .then(function (data) {
        if (notify_auto_api(data)) {
            setFormValuesFromUrl();
        }
    });
}

function resolveAlert(alert_id) {
    changeStatusAlert(alert_id, 'Resolved');
}

function closeAlert(alert_id) {
    changeStatusAlert(alert_id, 'Closed');
}

function changeStatusAlert(alert_id, status_name) {
    let status_id = getAlertStatusId(status_name);

    let data = {
        'alert_status_id': status_id
    }
    updateAlert(alert_id, data, true);
}


function setAlertOwnerToMe(alert_id) {
    data = {
        'alert_owner_id': user_id
    }
    updateAlert(alert_id, data, true);
}

async function changeAlertOwner(alertId) {
  // Fetch the user list from the endpoint
  const usersReq = await get_request_api('/manage/users/list');

  if (!notify_auto_api(usersReq, true)) { return; };

  users = usersReq.data;

  // Populate the select element with the fetched user list
  const userSelect = $('#changeOwnerAlertSelect');
  userSelect.empty();
  users.forEach((user) => {
    userSelect.append(`<option value="${user.user_id}">${user.user_name}</option>`);
  });

  $('#alertIDAssignModal').text(alertId);

  // Show the modal
  $('#changeAlertOwnerModal').modal('show');

  // Set up the form submission
  document.getElementById('assign-owner-button').onclick = async () => {
      // Get the selected user ID
      const newOwnerId = userSelect.val();

      // Send a POST request to the update endpoint
      updateAlert(alertId, {alert_owner_id: newOwnerId}, true)
      .then(() => {
            // Close the modal
            $('#changeAlertOwnerModal').modal('hide');
      });
  };
}


async function changeBatchAlertOwner(alertId) {

    const selectedAlerts = getBatchAlerts();
    if (selectedAlerts.length === 0) {
        notify_error('Please select at least one alert to perform this action on.');
        return;
    }

      // Fetch the user list from the endpoint
      const usersReq = await get_request_api('/manage/users/list');

      if (!notify_auto_api(usersReq, true)) { return; };

      users = usersReq.data;

      // Populate the select element with the fetched user list
      const userSelect = $('#changeOwnerAlertSelect');
      userSelect.empty();
      users.forEach((user) => {
        userSelect.append(`<option value="${user.user_id}">${user.user_name}</option>`);
      });

      $('#alertIDAssignModal').text(alertId);

      // Show the modal
      $('#changeAlertOwnerModal').modal('show');

      // Set up the form submission
      document.getElementById('assign-owner-button').onclick = async () => {
          // Get the selected user ID
          const newOwnerId = userSelect.val();

          // Send a POST request to the update endpoint
          updateBatchAlerts({alert_owner_id: newOwnerId})
          .then(() => {
                // Close the modal
                $('#changeAlertOwnerModal').modal('hide');
          });
      };
}


async function updateAlert(alert_id, data = {}, do_refresh = false) {
  data['csrf_token'] = $('#csrf_token').val();
  return post_request_api('/alerts/update/' + alert_id, JSON.stringify(data)).then(function (data) {
    if (notify_auto_api(data)) {
      if (do_refresh) {
        setFormValuesFromUrl();
        setTimeout(() => {
          const updatedAlertElement = $(`#alertCard-${alert_id}`);
          if (updatedAlertElement.length) {
            $('html, body').animate({
              scrollTop: updatedAlertElement.offset().top - 60
            }, 300);
            $(`#alertCard-${alert_id}`).addClass('fade-it');
          }
        }, 200);
      }
    }
  });
}



function setFormValuesFromUrl() {
  const queryParams = new URLSearchParams(window.location.search);
  const form = $('#alertFilterForm');
  const ajaxCalls = [];

  queryParams.forEach((value, key) => {
    const input = form.find(`[name="${key}"]`);
    if (input.length > 0) {
      if (input.prop('type') === 'checkbox') {
        input.prop('checked', value in ['true', 'y', 'yes', '1', 'on']);
      } else if (input.is('select') && selectsConfig[input.attr('id')]) {
        const ajaxCall = new Promise((resolve, reject) => {
          input.one('click', function () {
            fetchSelectOptions(input.attr('id'), selectsConfig[input.attr('id')]).then(() => {
              input.val(value);
              resolve();
            }).catch(error => {
              console.error(error);
              reject(error);
            });
          }).trigger('click');
        });
        ajaxCalls.push(ajaxCall);
      } else {
        input.val(value);
      }
    }
  });

  Promise.all(ajaxCalls)
    .then(() => {
      form.trigger('submit');
    })
    .catch(error => {
      console.error('Error setting form values:', error);
    });
}


function fetchSelectOptions(selectElementId, configItem) {
  return new Promise((resolve, reject) => {
    get_request_api(configItem.url)
      .then(function (data) {
        if (!notify_auto_api(data, true)) {
          reject('Failed to fetch options');
          return;
        }
        const selectElement = $(`#${selectElementId}`);
        selectElement.empty();
        selectElement.append($('<option>', {
          value: null,
          text: ''
        }));

        data.data.forEach(function (item) {
          selectElement.append($('<option>', {
            value: item[configItem.id],
            text: item[configItem.name]
          }));
        });
        resolve();
      });
  });
}

function getBatchAlerts() {
    const selectedAlerts = [];
    $('.tickbox input[type="checkbox"]').each(function() {
        if ($(this).is(':checked')) {
          const alertId = $(this).data('alert-id');
          selectedAlerts.push(alertId);
        }
    });
    return selectedAlerts;
}

function changeStatusBatchAlerts(status_name) {
    const data = {
        'alert_status_id': getAlertStatusId(status_name)
    }

    updateBatchAlerts(data);
}

async function updateBatchAlerts(data_content= {}) {
    const selectedAlerts = getBatchAlerts();
    if (selectedAlerts.length === 0) {
        notify_error('Please select at least one alert to perform this action on.');
        return;
    }

    const data = {
        'alert_ids': selectedAlerts,
        'csrf_token': $('#csrf_token').val(),
        'updates': data_content
    };

    return post_request_api('/alerts/batch/update', JSON.stringify(data)).then(function (data) {
        if (notify_auto_api(data)) {
            setFormValuesFromUrl();
        }
    });

}

$(document).ready(function () {
    for (const [selectElementId, configItem] of Object.entries(selectsConfig)) {
        $(`#${selectElementId}`).one('click', function () {
          fetchSelectOptions(selectElementId, configItem)
            .catch(error => console.error(error));
        });
      }
    setFormValuesFromUrl();
    getAlertStatusList();

      $('#toggle-selection-mode').on('click', function() {
        // Toggle the 'selection-mode' class on the body element
        $('body').toggleClass('selection-mode');

        // Check if the selection mode is active
        const selectionModeActive = $('body').hasClass('selection-mode');

        // Update the button text
        $(this).text(selectionModeActive ? 'Cancel' : 'Select');

        // Toggle the display of avatars, tickboxes and selection-related buttons
        $('.alert-card-selectable').each(function() {
          const avatarTickboxWrapper = $(this).find('.avatar-tickbox-wrapper');
          avatarTickboxWrapper.find('.avatar-wrapper').toggle(!selectionModeActive);
          avatarTickboxWrapper.find('.tickbox').toggle(selectionModeActive);
        });

        $('#select-deselect-all').toggle(selectionModeActive).text('Select all');
        $('#alerts-batch-actions').toggle(selectionModeActive);
      });

      $('#select-deselect-all').on('click', function() {
        const allSelected = $('.tickbox input[type="checkbox"]:not(:checked)').length === 0;

        $('.tickbox input[type="checkbox"]').prop('checked', !allSelected);
        $(this).text(allSelected ? 'Select all' : 'Deselect all');
      });


});