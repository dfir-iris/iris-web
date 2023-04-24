let sortOrder ;

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

async function fetchMultipleAlerts(alertIds) {
    const response = get_raw_request_api(`/alerts/filter?cid=${get_caseid()}&alert_ids=${alertIds.join(',')}`);
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

function appendLabels(list, items, itemType) {
    items.forEach((item) => {
        const label = $('<label></label>').addClass('d-block');
        const input = $('<input>').attr({
            type: 'checkbox',
            name: itemType,
            value: item[itemType + '_name'] || item[itemType + '_value'],
            id: item[itemType + '_uuid'],
            checked: true,
        });
        label.append(input);
        label.append(` ${item[itemType + '_name'] || item[itemType + '_value']}`);
        list.append(label);
    });
}

function toggleSelectDeselect(toggleButton, listSelector) {
    let allChecked = true;
    $(listSelector).each(function () {
        if (!$(this).prop("checked")) {
            allChecked = false;
        }
        $(this).prop("checked", !$(this).prop("checked"));
    });

    if (allChecked) {
        toggleButton.text("Select All");
    } else {
        toggleButton.text("Deselect All");
    }
}

function unlinkAlertFromCase(alert_id, case_id) {

    do_deletion_prompt(`Unlink alert #${alert_id} from the case #${case_id}?`, true)
        .then( () => {
            unlinkAlertFromCaseRequest(alert_id, case_id)
                .then((data) => {
                    if (!notify_auto_api(data)) {
                        return;
                    }
                    refreshAlert(alert_id);
                });
    });

}

async function unlinkAlertFromCaseRequest(alert_id, case_id) {
    return await post_request_api(`/alerts/unmerge/${alert_id}`, JSON.stringify({
        target_case_id: case_id,
        csrf_token: $('#csrf_token').val()
    }));
}

async function mergeMultipleAlertsModal() {
    const selectedAlerts = getBatchAlerts();
    const escalateButton = $("#escalateOrMergeButton");
    if (selectedAlerts.length === 0) {
        notify_error('Please select at least one alert to perform this action on.');
        return;
    }
    const alertDataReq = await fetchMultipleAlerts(selectedAlerts);

    if (!notify_auto_api(alertDataReq, true)) {
        return;
    }

    const ioCsList = $("#ioCsList");
    const assetsList = $("#assetsList");

    // Configure the modal for both escalation and merging
    $('#escalateModalLabel').text('Merge multiple alerts in a new case');
    $('#escalateModalExplanation').text('These alerts will be merged into a new case. Set the case title and select the IOCs and Assets to escalate into the case.');
    $('#modalAlertTitleContainer').hide();

    $('#modalEscalateCaseTitle').val(`[ALERT] Escalation of ${selectedAlerts.length} alerts`);
    $('#modalEscalateCaseTitleContainer').show();

    escalateButton.attr("data-merge", false);
    $('#mergeAlertCaseSelectSection').hide();

    const case_tags = $('#case_tags');

    case_tags.val('')
    case_tags.amsifySuggestags({
        printValues: false,
        suggestions: []
    });

    // Load case options for merging
    var options = {
        ajax: {
            url: '/context/search-cases' + case_param(),
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

    // Clear the lists
    ioCsList.html("");
    assetsList.html("");

    if (!notify_auto_api(alertDataReq, true)) {
        return;
    }

    let alertsData = alertDataReq.data;

    for (let i = 0; i < alertsData.length; i++) {
        let alertData = alertsData[i];
        if (alertData.iocs.length !== 0) {
            appendLabels(ioCsList, alertData.iocs, 'ioc');
        }
        if (alertData.assets.length !== 0) {
            appendLabels(assetsList, alertData.assets, 'asset');
        }
    }

    escalateButton.attr("data-merge", true);
    escalateButton.attr("data-alert-id", selectedAlerts.join(','));
    escalateButton.attr("data-multi-merge", true);
    $('#escalateModal').modal('show');

    $("input[type='radio'][name='mergeOption']:checked").trigger("change");

    $("input[type='radio'][name='mergeOption']").on("change", function () {
        if ($(this).val() === "existing_case") {
            $('#escalateModalLabel').text(`Merge ${selectedAlerts.length} alerts in an existing case`);
            $('#escalateModalExplanation').text('These alerts will be merged into the selected case. Select the IOCs and Assets to merge into the case.');
            $('#mergeAlertCaseSelectSection').show();
            $('#modalEscalateCaseTitleContainer').hide();
            $('#mergeAlertCaseSelect').selectpicker('refresh');
            $('#mergeAlertCaseSelect').selectpicker('val', get_caseid());
            escalateButton.attr("data-merge", true);
        } else {
            $('#escalateModalLabel').text(`Merge ${selectedAlerts.length} alerts in new case`);
            $('#escalateModalExplanation').text('This alert will be merged into a new case. Set the case title and select the IOCs and Assets to merge into the case.');
            $('#mergeAlertCaseSelectSection').hide();
            $('#modalEscalateCaseTitleContainer').show();
            escalateButton.attr("data-merge", false);
        }
    });

}

async function mergeAlertModal(alert_id) {
    const escalateButton = $("#escalateOrMergeButton");
    escalateButton.attr("data-alert-id", alert_id);

    const alertDataReq = await fetchAlert(alert_id);
    const ioCsList = $("#ioCsList");
    const assetsList = $("#assetsList");

    if (!notify_auto_api(alertDataReq, true)) {
        return;
    }

    $("#modalAlertId").val(alert_id);
    $("#modalAlertTitle").val(alertDataReq.data.alert_title);

    // Configure the modal for both escalation and merging
    $('#escalateModalLabel').text(`Merge alert #${alert_id} in a new case`);
    $('#escalateModalExplanation').text('This alert will be escalated into a new case. Set a title and select the IOCs and Assets to escalate into the case.');

    $('#modalEscalateCaseTitle').val(`[ALERT] ${alertDataReq.data.alert_title}`);
    $('#modalEscalateCaseTitleContainer').show();

    escalateButton.attr("data-merge", false);
    $('#mergeAlertCaseSelectSection').hide();

    const case_tags = $('#case_tags');

    case_tags.val(alertDataReq.data.alert_tags)
    case_tags.amsifySuggestags({
        printValues: false,
        suggestions: []
    });

    // Load case options for merging
    var options = {
        ajax: {
            url: '/context/search-cases' + case_param(),
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

    // Clear the lists
    ioCsList.html("");
    assetsList.html("");

    if (!notify_auto_api(alertDataReq, true)) {
        return;
    }

    let alertData = alertDataReq.data;

    if (alertData.iocs.length !== 0) {
        appendLabels(ioCsList, alertData.iocs, 'ioc');
        $("#toggle-iocs").on("click", function () {
            toggleSelectDeselect($(this), "#ioCsList input[type='checkbox']");
        });
        $("#ioc-container").show();
    } else {
        $("#ioc-container").show();
    }

    if (alertData.assets.length !== 0) {
        appendLabels(assetsList, alertData.assets, 'asset');
        $("#toggle-assets").on("click", function () {
            toggleSelectDeselect($(this), "#assetsList input[type='checkbox']");
        });
        $("#asset-container").show();
    } else {
        $("#asset-container").hide();
    }

    $("#escalateModal").modal("show");

    $("input[type='radio'][name='mergeOption']:checked").trigger("change");

    $("input[type='radio'][name='mergeOption']").on("change", function () {
        if ($(this).val() === "existing_case") {
            $('#escalateModalLabel').text(`Merge alert #${alert_id} in existing case`);
            $('#escalateModalExplanation').text('This alert will be merged into the selected case. Select the IOCs and Assets to merge into the case.');
            $('#mergeAlertCaseSelectSection').show();
            $('#modalEscalateCaseTitleContainer').hide();
            $('#mergeAlertCaseSelect').selectpicker('refresh');
            $('#mergeAlertCaseSelect').selectpicker('val', get_caseid());
            escalateButton.attr("data-merge", true);
        } else {
            $('#escalateModalLabel').text(`Merge alert #${alert_id} in new case`);
            $('#escalateModalExplanation').text('This alert will be merged into a new case. Set the case title and select the IOCs and Assets to merge into the case.');
            $('#mergeAlertCaseSelectSection').hide();
            $('#modalEscalateCaseTitleContainer').show();
            escalateButton.attr("data-merge", false);
        }
    });
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

function fetchSmartRelations(alert_id) {
    $('input[value="open_alerts"]').prop('checked', true);
    $('input[value="closed_alerts"]').prop('checked', false);
    $('input[value="open_cases"]').prop('checked', false);
    $('input[value="closed_cases"]').prop('checked', false);

    fetchSimilarAlerts(alert_id, false, true, false,
        false, false);
}

function buildAlertLink(alert_id){
    const current_path = location.protocol + '//' + location.host
    return current_path + '/alerts' + case_param() + '&alert_id=' + alert_id;
}

function copyAlertLink(alert_id) {
    const link = buildAlertLink(alert_id);
    navigator.clipboard.writeText(link).then(function() {
        notify_success('Link copied');
    }, function(err) {
        notify_error('Can\'t copy link. I printed it in console.');
        console.error('Shared link', err);
    });
}

function copyMDAlertLink(alert_id){
    const link = `[<i class="fa-solid fa-bell"></i> #${alert_id}](${buildAlertLink(alert_id)})`;
    navigator.clipboard.writeText(link).then(function() {
        notify_success('MD link copied');
    }, function(err) {
        notify_error('Can\'t copy link. I printed it in console.');
        console.error('Shared link', err);
    });
}

function getAlertOffset(element) {
  const rect = element.getBoundingClientRect();
  return {
    left: rect.left,
    top: rect.top + window.scrollY,
  };
}

function createNetwork(alert, relatedAlerts, containerId, containerConfigureId) {
  const { nodes, edges } = relatedAlerts;

  const data = {
    nodes: new vis.DataSet(nodes),
    edges: new vis.DataSet(edges),
  };

  const options = {
    edges: {
      smooth: {
            enabled: true,
            type: 'continuous',
            roundness: 0.5
        }
    },
    layout: {
        randomSeed: 2,
        improvedLayout: true
    },
    interaction: {
      hideEdgesOnDrag: false,
        tooltipDelay: 100
    },
    height: (window.innerHeight- 250) + "px",
    clickToUse: true,
    physics: {
        forceAtlas2Based: {
          gravitationalConstant: -167,
          centralGravity: 0.04,
          springLength: 0,
          springConstant: 0.02,
          damping: 0.9
        },
        minVelocity: 0.41,
        solver: "forceAtlas2Based",
        timestep: 0.45
    }
  };

    const container = document.getElementById(containerId);
    const network = new vis.Network(container, data, options);

    network.on("stabilizationIterationsDone", function () {
        network.setOptions( { physics: false } );
    });

    let selectedNodeId = null;
    let node_type = null;
    let node_id = null;


    network.on('oncontext', (event) => {
      event.event.preventDefault();

      const nodeId = network.getNodeAt(event.pointer.DOM);

      if (nodeId) {
        selectedNodeId = nodeId;
        node_type = selectedNodeId.split('_')[0];
        node_id = selectedNodeId.split('_')[1];

        if (node_type === 'alert') {
            // Get the offset of the container element.
            const containerOffset = getAlertOffset(container);

            const x = event.pointer.DOM.x + 160;
            const y = containerOffset.top + event.pointer.DOM.y;

            const contextMenu = document.getElementById('context-menu-relationships');
            contextMenu.style.left = `${x}px`;
            contextMenu.style.top = `${y}px`;
            contextMenu.classList.remove('hidden');

            $('#view-alert').data('alert-id', node_id);

        }
      }
  });

    document.addEventListener('click', () => {
      const contextMenu = document.getElementById('context-menu-relationships');
      contextMenu.classList.add('hidden');
    });

}

function viewAlertGraph() {
    const alert_id = $(this).data('alert-id');

    window.open(`/alerts?alert_ids=${alert_id}&cid=${get_caseid()}`);
}


function fetchSimilarAlerts(alert_id,
  refresh = false,
  fetch_open_alerts = true,
  fetch_closed_alerts = false,
  fetch_open_cases = false,
  fetch_closed_cases = false
    ) {
      const similarAlertsElement = $(`#similarAlerts-${alert_id}`);
      if (!similarAlertsElement.html() || refresh) {
        // Build the query string with the new parameters
        const queryString = new URLSearchParams({
          'open-alerts': fetch_open_alerts,
          'closed-alerts': fetch_closed_alerts,
          'open-cases': fetch_open_cases,
          'closed-cases': fetch_closed_cases,
        }).toString();

        get_request_api(`/alerts/similarities/${alert_id}?${queryString}`)
          .done((data) => {
            createNetwork(alert_id, data.data, `similarAlerts-${alert_id}`, `graphConfigure-${alert_id}`);
          });
      }
}



function escalateOrMergeAlert(alert_id, merge = false, batch = false) {

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
        case_tags: $('#case_tags').val(),
        csrf_token: $("#csrf_token").val()
    };

    let url =  batch ? `/alerts/batch/`: `/alerts/`;

    if (merge) {
        requestBody.target_case_id = $('#mergeAlertCaseSelect').val();
        url += batch ? 'merge' : `merge/${alert_id}`;
    } else {
        requestBody.case_title = $('#modalEscalateCaseTitle').val();
        url += batch ? 'escalate' : `escalate/${alert_id}`;
    }

    if (batch) {
        requestBody.alert_ids = alert_id;
    }

    post_request_api(url, JSON.stringify(requestBody))
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

function alertStatusToColor(status) {
    switch (status) {
        case 'Closed':
            return 'alert-card-done';
        case 'Dismissed':
            return 'alert-card-done';
        case 'Merged':
            return 'alert-card-done';
        case 'Escalated':
            return 'alert-card-done';
        case 'New':
            return 'alert-card-new';
        default:
            return '';
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

function getFiltersFromUrl() {
    const formData = new FormData($('#alertFilterForm')[0]);
    return Object.fromEntries(formData.entries());
}

function renderAlert(alert, expanded=false) {
  const colorSeverity = alert_severity_to_color(alert.severity.severity_name);
  const alert_color = alertStatusToColor(alert.status.status_name);

  return `
        <div class="card alert-card full-height alert-card-selectable ${alert_color}" id="alertCard-${alert.alert_id}">
            <div class="card-body" >
              <div class="d-flex">
                <div class="avatar-group mt-3 ${alert.owner ? '': 'ml-2 mr-2' }">
                    <div class="avatar-tickbox-wrapper">
                       <div class="avatar-wrapper">
                            <div class="avatar cursor-pointer">
                                <span class="avatar-title alert-m-title alert-similarity-trigger rounded-circle bg-${colorSeverity}" 
                                data-toggle="collapse" data-target="#additionalDetails-${alert.alert_id}">
                                <i class="fa-solid fa-fire"></i></span>

                            </div>
                            ${alert.owner ? get_avatar_initials(alert.owner.user_name, true, `changeAlertOwner(${alert.alert_id})`) : 
                                `<div title="Assign to me" class="avatar avatar-sm" onclick="updateAlert(${alert.alert_id}, {alert_owner_id: userWhoami.user_id}, true);"><span class="avatar-title avatar-iris rounded-circle btn-alert-primary" style="cursor:pointer;"><i class="fa-solid fa-hand"></i></span></div>`}
                            <div class="envelope-icon">
                                ${ alert.status ? `<span class="badge alert-bade-status badge-pill badge-light">${alert.status.status_name}</span>`: ''} 
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
                  <div id="additionalDetails-${alert.alert_id}" class="collapse mt-4 ${expanded? 'show': ''} alert-collapsible">
                    <div class="card-no-pd mt-2">
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
                        
                        <div class="separator-solid"></div>
                        <h3 class="title mb-3"><strong>Alert note</strong></h3>
                        <pre id=alertNote-${alert.alert_id}>${alert.alert_note}</pre>
                        
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
                        
                        <div class="separator-solid"></div>
                        <h3 class="title mt-3 mb-3"><strong>Relationships</strong></h3>
                        <button class="btn btn-sm btn-outline-dark" type="button" data-toggle="collapse" data-target="#relationsAlert-${alert.alert_id}" 
                        aria-expanded="false" aria-controls="relationsAlert-${alert.alert_id}" onclick="fetchSmartRelations(${alert.alert_id});">Toggle Relations</button>
                        <div class="collapse mt-3" id="relationsAlert-${alert.alert_id}">
                            The following relationships are automatically generated by IRIS based on the alert's IOCs and assets 
                            in the system. They are an indication only and may not be accurate. 
                            
                            <div class="selectgroup selectgroup-pills mt-4">
                                <label class="selectgroup-item">
                                    <input type="checkbox" name="value" value="open_alerts" class="selectgroup-input filter-graph-alert-checkbox" onclick="refreshAlertRelationships(${alert.alert_id});">
                                    <span class="selectgroup-button">Show open alerts</span>
                                </label>
                                <label class="selectgroup-item">
                                    <input type="checkbox" name="value" value="closed_alerts" class="selectgroup-input filter-graph-alert-checkbox" onclick="refreshAlertRelationships(${alert.alert_id})">
                                    <span class="selectgroup-button">Show closed alerts</span>
                                </label>
                                <label class="selectgroup-item">
                                    <input type="checkbox" name="value" value="open_cases" class="selectgroup-input filter-graph-alert-checkbox" onclick="refreshAlertRelationships(${alert.alert_id})">
                                    <span class="selectgroup-button">Show open cases</span>
                                </label>
                                <label class="selectgroup-item">
                                    <input type="checkbox" name="value" value="closed_cases" class="selectgroup-input filter-graph-alert-checkbox" onclick="refreshAlertRelationships(${alert.alert_id})">
                                    <span class="selectgroup-button">Show closed cases</span>
                                </label>
                            </div>
                            <div id="similarAlerts-${alert.alert_id}" class="mt-4 similar-alert-graph"></div>
                        </div>

                    
                        <!-- Alert IOCs section -->
                        ${
                          alert.iocs && alert.iocs.length > 0
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
                                                 ${alert.iocs
                                  .map(
                                      (ioc) => `
                                                     <tr>
                                                       <td>${ioc.ioc_value}</td>
                                                       <td>${ioc.ioc_description}</td>
                                                       <td>${ioc.ioc_type ? ioc.ioc_type.type_name : '-'}</td>
                                                       <td>${ioc.ioc_tlp ? ioc.ioc_tlp : '-'}</td>
                                                       <td>${ioc.ioc_tags ? ioc.ioc_tags.split(',').map((tag) => `<span class="badge badge-pill badge-light ml-1"><i class="fa fa-tag mr-1"></i>${tag}</span>`).join('') : ''}</td>
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
                        alert.assets && alert.assets.length > 0
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
                                     ${alert.assets
                      .map(
                          (asset) => `
                                         <tr>
                                           <td>${asset.asset_name ? asset.asset_name : '-'}</td>
                                           <td>${asset.asset_description ? asset.asset_description : '-'}</td>
                                           <td>${asset.asset_type ? asset.asset_type.asset_name : '-'}</td>
                                           <td>${asset.asset_domain ? asset.asset_domain : '-'}</td>
                                           <td>${asset.asset_ip ? asset.asset_ip : '-'}</td>
                                           <td>${asset.asset_tags ? asset.asset_tags.split(',').map((tag) => `<span class="badge badge-pill badge-light ml-1"><i class="fa fa-tag mr-1"></i>${tag}</span>`).join('') : ''}</td>
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
                               <button class="btn btn-sm btn-outline-dark" type="button" data-toggle="collapse" data-target="#rawAlert-${alert.alert_id}" 
                               aria-expanded="false" aria-controls="rawAlert-${alert.alert_id}">Toggle Raw Alert</button>
                               <div class="collapse mt-3" id="rawAlert-${alert.alert_id}">
                                 <pre class="pre-scrollable">${JSON.stringify(alert.alert_source_content, null, 2)}</pre>
                               </div>`
                  : ""
          }
                        
                        </div>
                      </div>
                  </div>
                  
                  ${alert.cases ? `<div class='row mt-4'>` + alert.cases.map((case_) => `
                    <div class="dropdown ml-2 d-inline-block">
                          <a class="bg-transparent ml-2" title="Merged in case #${case_}" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false" href="javascript:void(0)">
                              <span aria-hidden="true"><i class="fa-solid fa-link"></i>#${case_}</span>
                          </a>
                          <div class="dropdown-menu">
                            <a class="dropdown-item" href="/case?cid=${case_}" target="_blank"><i class="fa-solid fa-eye mr-2"></i> View case #${case_}</a>    
                            <div class="dropdown-divider"></div>
                            <a class="dropdown-item text-danger" href="javascript:void(0)" onclick="unlinkAlertFromCase(${alert.alert_id}, ${case_})"><i class="fa-solid fa-unlink mr-2"></i>Unlink alert from case #${case_}</a>
                          </div>
                    </div>
                  `).join('') + '</div>' : '<div class="mb-4"></div>'}

                  <div class="">                    
                    <span title="Alert source event time"><b><i class="fa-regular fa-calendar-check"></i></b>
                    <small class="text-muted ml-1">${alert.alert_source_event_time}</small></span>
                    <span title="Alert severity"><b class="ml-3"><i class="fa-solid fa-bolt"></i></b>
                      <small class="text-muted ml-1" id="alertSeverity-${alert.alert_id}" data-severity-id="${alert.severity.severity_id}">${alert.severity.severity_name}</small></span>
                    <span title="Alert source"><b class="ml-3"><i class="fa-solid fa-cloud-arrow-down"></i></b>
                      <small class="text-muted ml-1">${alert.alert_source || 'Unspecified'}</small></span>
                    <span title="Alert client"><b class="ml-3"><i class="fa-regular fa-circle-user"></i></b>
                      <small class="text-muted ml-1 mr-2">${alert.customer.customer_name || 'Unspecified'}</small></span>
                    ${alert.classification && alert.classification.name_expanded ? `<span class="badge badge-pill badge-light" title="Classification" id="alertClassification-${alert.alert_id}" data-classification-id="${alert.classification.id}"><i class="fa-solid fa-shield-virus mr-1"></i>${alert.classification.name_expanded}</span>`: ''}
                    ${alert.alert_tags ? alert.alert_tags.split(',').map((tag) => `<span class="badge badge-pill badge-light ml-1"><i class="fa fa-tag mr-1"></i>${tag}</span>`).join('') + `<div style="display:none;" id="alertTags-${alert.alert_id}">${alert.alert_tags}</div>` : ''}
                                    
                  </div>
                </div>
                
                <div class="float-right ml-2">
                <button type="button" class="btn bg-transparent btn-sm mt-1" onclick="comment_element(${alert.alert_id}, 'alerts', true)" title="Comments">
                    <span class="btn-label">
                        <i class="fa-solid fa-comments"></i><span class="notification" id="object_comments_number_${alert.alert_id}">${alert.comments.length || ''}</span>
                    </span>
                </button>
                <button class="btn btn-sm bg-transparent" type="button" onclick="editAlert(${alert.alert_id})"><i class="fa fa-pencil"></i></button>
                  <button class="btn bg-transparent" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                      <span aria-hidden="true"><i class="fas fa-ellipsis-v"></i></span>
                  </button>
                  <div class="dropdown-menu" role="menu">
                    <a href="javascript:void(0)" class="dropdown-item" onclick="copyAlertLink(${alert.alert_id});return false;"><small class="fa fa-share mr-2"></small>Share</a>
                    <a href="javascript:void(0)" class="dropdown-item" onclick="copyMDAlertLink(${alert.alert_id});return false;"><small class="fa-brands fa-markdown mr-2"></small>Markdown Link</a>
                    <div class="dropdown-divider"></div>
                    <a href="javascript:void(0)" class="dropdown-item text-danger" onclick="delete_alert(${alert.alert_id});"><small class="fa fa-trash mr-2"></small>Delete alert</a>
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
                            <a class="dropdown-item" href="javascript:void(0)" onclick="updateAlert(${alert.alert_id}, {alert_owner_id: userWhoami.user_id}, true);">Assign to me</a>
                            <a class="dropdown-item" href="javascript:void(0)" onclick="changeAlertOwner(${alert.alert_id});">Assign</a>
                        </div>
                    </div>
                    
                    <div class="dropdown ml-2 d-inline-block">
                        <button type="button" class="btn btn-alert-primary btn-sm dropdown-toggle" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                            Set status
                        </button>
                        <div class="dropdown-menu">
                            <a class="dropdown-item" href="javascript:void(0)" onclick="changeStatusAlert(${alert.alert_id}, 'New');">New</a>
                            <a class="dropdown-item" href="javascript:void(0)" onclick="changeStatusAlert(${alert.alert_id}, 'In progress');">In progress</a>
                            <a class="dropdown-item" href="javascript:void(0)" onclick="changeStatusAlert(${alert.alert_id}, 'Pending');">Pending</a>
                            <a class="dropdown-item" href="javascript:void(0)" onclick="changeStatusAlert(${alert.alert_id}, 'Closed');">Closed</a>
                            <a class="dropdown-item" href="javascript:void(0)" onclick="changeStatusAlert(${alert.alert_id}, 'Merged');">Merged</a>
                        </div>
                    </div>
                    ${alert.status.status_name === 'Closed' ? `
                        <button type="button" class="btn btn-alert-success btn-sm ml-2" onclick="changeStatusAlert(${alert.alert_id}, 'In progress');">Set in progress</button>
                    `: ` 
                    <button type="button" class="btn btn-alert-danger btn-sm ml-2" onclick="editAlert(${alert.alert_id}, true);">Close with note</button>
                    <button type="button" class="btn btn-alert-danger btn-sm ml-2" onclick="changeStatusAlert(${alert.alert_id}, 'Closed');">Close</button>
                    `}
                </div>
          </div>    
          </div>
  `;

}

async function refreshAlert(alertId, alertData, expanded=false) {
    if (alertData === undefined) {
        const alertDataReq = await fetchAlert(alertId);
        if (!notify_auto_api(alertDataReq, true)) {
            return;
        }
        alertData = alertDataReq.data;
    }

    const alertElement = $(`#alertCard-${alertId}`);
    const alertHtml = renderAlert(alertData, expanded);
    alertElement.replaceWith(alertHtml);
}

async function updateAlerts(page, per_page, filters = {}, paging=false){
  if (sortOrder === undefined) { sortOrder = 'desc'; }

  if (paging) {
      filters = getFiltersFromUrl();
  }

  const filterString = objectToQueryString(filters);
  const data = await fetchAlerts(page, per_page, filterString, sortOrder);

  if (!notify_auto_api(data, true)) {
    return;
  }
  const alerts = data.data.alerts;

  // Check if the selection mode is active
   const selectionModeActive = $('body').hasClass('selection-mode');
   selectionModeActive ? $('body').removeClass('selection-mode') : '';
   $('#toggle-selection-mode').text('Select');
   $('body').removeClass('selection-mode');
   $('#select-deselect-all').hide();
   $('#alerts-batch-actions').hide();

  // Clear the current alerts list
  const alertsContainer = $('.alerts-container');
  const queryParams = new URLSearchParams(window.location.search);
  const isExpanded = queryParams.get('is-expanded') === 'true';

  alertsContainer.html('');
  if (alerts.length === 0) {
    // Display "No results" message when there are no alerts
    alertsContainer.append('<div class="ml-auto mr-auto">No results</div>');
  } else {

      // Add the fetched alerts to the alerts container
      alerts.forEach((alert) => {
          const alertElement = $('<div></div>');

          const alertHtml = renderAlert(alert, isExpanded);
          alertElement.html(alertHtml);
          alertsContainer.append(alertElement);
      });
  }

  // Update the pagination links
  const currentPage = page;
  const totalPages = Math.ceil(data.data.total / per_page);
  createPagination(currentPage, totalPages, per_page, 'updateAlerts', '.pagination-container');

  // Update the URL with the filter parameters
  queryParams.set('page', page);
  queryParams.set('per_page', per_page);
  let filter_tags_info = [];

  for (const key in filters) {
    if (filters.hasOwnProperty(key)) {
      if (filters[key] === '') {
        queryParams.delete(key);
      } else {
        queryParams.set(key, filters[key]);
        filter_tags_info.push(`  
          <span class="badge badge-light">
            <i class="fa-solid fa-magnifying-glass mr-1"></i>${key}: ${filterXSS(filters[key])}
            <span class="tag-delete-alert-filter" data-filter-key="${key}" style="cursor: pointer;" title="Remove filter"><i class="fa-solid fa-xmark ml-1"></i></span>
          </span>
        `)
      }
    }
  }

  queryParams.set('sort', sortOrder);

  history.replaceState(null, null, `?${queryParams.toString()}`);

  $('#alertsInfoFilter').text(`${data.data.total} Alert${ data.data.total > 1 ? 's' : ''} ${ filterString ? `(filtered)` : '' }`);

  if (filter_tags_info) {
    $('#alertsInfoFilterTags').html(filter_tags_info.join(' + '));
    $('#alertsInfoFilterTags .tag-delete-alert-filter').on('click', function () {
      const filterKey = $(this).data('filter-key');
      delete filters[filterKey];
      queryParams.delete(filterKey);
      $(`#${filterKey}`).val('');

      resetSavedFilters(queryParams, false);

      history.replaceState(null, null, `?${queryParams.toString()}`);
      updateAlerts(page, per_page, filters);
    });
  } else {
    $('#alertsInfoFilterTags').html('');
  }

  filterString || queryParams.get('filter_id') ? $('#resetFilters').show() : $('#resetFilters').hide();

  alertsContainer.show();
}

$('#alertsPerPage').on('change', (e) => {
  const per_page = parseInt(e.target.value, 10);
  updateAlerts(1, per_page, undefined, sortOrder); // Update the alerts list with the new 'per_page' value and reset to the first page
});


$('#orderAlertsBtn').on('click', function () {
  sortOrder = sortOrder === 'desc' ? 'asc' : 'desc';
  const iconClass = sortOrder === 'desc' ? 'fas fa-arrow-up-short-wide' : 'fas fa-arrow-up-wide-short';

  $('#orderAlertsBtn i').attr('class', iconClass);

  const queryParams = new URLSearchParams(window.location.search);
  let page_number = parseInt(queryParams.get('page'));
  let per_page = parseInt(queryParams.get('per_page'));


  const formData = new FormData($('#alertFilterForm')[0]);
  const filters = Object.fromEntries(formData.entries());

  updateAlerts(page_number, per_page, filters);
});

function refreshAlerts(){
    const queryParams = new URLSearchParams(window.location.search);
    let page_number = parseInt(queryParams.get('page'));
    let per_page = parseInt(queryParams.get('per_page'));

    const formData = new FormData($('#alertFilterForm')[0]);
    const filters = Object.fromEntries(formData.entries());

    updateAlerts(page_number, per_page, filters)
        .then(() => {
            notify_success('Refreshed');
            $('#newAlertsBadge').text(0).hide();
        });
}

function toggleCollapseAllAlerts() {
    const toggleAllBtn = $('#toggleAllAlertsBtn');
    const isExpanded = toggleAllBtn.data('is-expanded') || false;

    collapseAlerts(!isExpanded);

    const queryParams = new URLSearchParams(window.location.search);
    queryParams.set('is-expanded', !isExpanded);
    window.history.replaceState(null, '', '?' + queryParams.toString());
}

function collapseAlerts(isExpanded) {
    const alertsContainer = $('.alert-collapsible');
    const toggleAllBtn = $('#toggleAllAlertsBtn');

    if (isExpanded) {
        alertsContainer.collapse('show');
        toggleAllBtn.text('Collapse All');
        toggleAllBtn.data('is-expanded', true);
    } else {
        alertsContainer.collapse('hide');
        toggleAllBtn.text('Expand All');
        toggleAllBtn.data('is-expanded', false);
    }
}

$('#alertFilterForm').on('submit', (e) => {
  e.preventDefault();

  // Get the filter values from the form
  const formData = new FormData(e.target);
  const filters = Object.fromEntries(formData.entries());

  const queryParams = new URLSearchParams(window.location.search);
  let per_page = parseInt(queryParams.get('per_page'));
  if (!per_page) {
      per_page = 10;
  }

  // Update the alerts list with the new filters and reset to the first page
  updateAlerts(1, per_page, filters);
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

    // Reset the saved filters dropdown
    resetSavedFilters(null);

  // Trigger the form submit event to fetch alerts with the updated filters
  form.trigger('submit');
});

function resetSavedFilters(queryParams = null, replaceState = true) {
    if (queryParams === null || queryParams === undefined) {
        queryParams = new URLSearchParams(window.location.search);
    }
    queryParams.delete('filter_id');
    if (replaceState) {
        window.history.replaceState(null, null, `?${queryParams.toString()}`);
    }
    $('.preset-dropdown-container').hide();
    $('#savedFilters').selectpicker('val', '');

    return queryParams;
}

$("#escalateOrMergeButton").on("click", () => {

    const alertId = $("#escalateOrMergeButton").data("alert-id");
  const merge = $("#escalateOrMergeButton").data("merge");
  const multiMerge = $("#escalateOrMergeButton").data("multi-merge");

  escalateOrMergeAlert(alertId, merge, multiMerge);

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

async function editAlert(alert_id, close=false) {

    const alertTag = $('#editAlertTags');
    const confirmAlertEdition = $('#confirmAlertEdition');

    alertTag.val($(`#alertTags-${alert_id}`).text())
    alertTag.amsifySuggestags({
     printValues: false,
     suggestions: []
    });
    $('#editAlertNote').val($(`#alertNote-${alert_id}`).text());

    if (close) {
        confirmAlertEdition.text('Close alert');
        $('.alert-edition-part').hide();
        $('#closeAlertModalLabel').text(`Close alert #${alert_id}`);
    } else {
        $('.alert-edition-part').show();
        $('#closeAlertModalLabel').text(`Edit alert #${alert_id}`);
        confirmAlertEdition.text('Save')
    }

    fetchSelectOptions('editAlertClassification', selectsConfig['alertClassificationFilter']).then(() => {
      $('#editAlertClassification').val($(`#alertClassification-${alert_id}`).data('classification-id'));
    }).catch(error => {
      console.error(error);
    });

    fetchSelectOptions('editAlertSeverity', selectsConfig['alertSeverityFilter']).then(() => {
      $('#editAlertSeverity').val($(`#alertSeverity-${alert_id}`).data('severity-id'));
    }).catch(error => {
      console.error(error);
    });

    $('#editAlertModal').modal('show');

    confirmAlertEdition.off('click').on('click', function () {
        let alert_note = $('#editAlertNote').val();
        let alert_tags = alertTag.val();

        let data = {
          alert_note: alert_note,
          alert_tags: alert_tags,
          alert_classification_id: $('#editAlertClassification').val(),
          alert_severity_id: $('#editAlertSeverity').val()
        };

        if (close) {
            data['alert_status_id'] = getAlertStatusId('Closed');
        }

        updateAlert(alert_id, data, true, true)
            .then(() => {
                $('#editAlertModal').modal('hide');
            });
    });
}

async function fetchSavedFilters() {
    const url = '/filters/alerts/list';
    return get_request_api(url)
        .then((data) => {
            if (notify_auto_api(data)) {
                const savedFiltersDropdown = $('#savedFiltersDropdown');

                savedFiltersDropdown.empty();

                let dropdownHtml = `
                    <select class="selectpicker" data-style="btn-sm" data-live-search="true" title="Select preset filter" id="savedFilters">
                `;

                data.data.forEach(filter => {
                    dropdownHtml += `
                                <option value="${filter.filter_id}" data-content='<div class="d-flex align-items-center"><span>${filter.filter_name} ${filter.filter_is_private ? '(private)' : ''}</span><div class="trash-wrapper hidden-trash"><i class="fas fa-trash delete-filter text-danger" id="dropfilter-id-${filter.filter_id}" title="Delete filter"></i></div></div>'>${filter.filter_name}</option>
                    `;
                });

                dropdownHtml += '</select>';

                savedFiltersDropdown.append(dropdownHtml);

                // Initialize the bootstrap-select component
                $('#savedFilters').selectpicker();

                // Add the event listener after the selectpicker is loaded
                $('#savedFilters').on('shown.bs.select', function () {
                    $('.trash-wrapper').removeClass('hidden-trash');
                    $('.delete-filter').off().on('click', function (event) {
                        event.preventDefault();
                        event.stopPropagation();

                        const filterId = $(this).attr('id').split('-')[2];

                        if (!filterId) return;

                        do_deletion_prompt(`Are you sure you want to delete filter #${filterId}?`, true)
                            .then((do_delete) => {
                                if (!do_delete) return;
                                const url = `/filters/delete/${filterId}`;
                                const data = {
                                    csrf_token: $('#csrf_token').val()
                                };
                                post_request_api(url, JSON.stringify(data))
                                    .then((data) => {
                                        if (notify_auto_api(data)) {
                                            fetchSavedFilters();
                                        }
                                    });
                        });
                    });
                }).on('hide.bs.select', function () {
                    $('.trash-wrapper').addClass('hidden-trash');
                });

                $('#savedFilters').on('change', function() {

                    const selectedFilterId = $('#savedFilters').val();
                    if (!selectedFilterId) return;

                    const url = `/filters/${selectedFilterId}`;

                    get_request_api(url)
                        .then((data) => {
                            if(!notify_auto_api(data, true)) return;
                            const queryParams = new URLSearchParams();
                            Object.entries(data.data.filter_data).forEach(([key, value]) => {
                                if (value !== '') {
                                    queryParams.set(key, value);
                                }
                            });

                            queryParams.set('filter_id', selectedFilterId);

                            // Update the URL and reload the page with the new filter settings
                            window.location.href = window.location.pathname + case_param() + '&' + queryParams.toString();
                        })
                });
            }
        });
}

$('#saveFilters').on('click', function () {
    $('#saveFilterModal').modal('show');
});

$('#saveFilterButton').on('click', function () {
    const filterData = $('#alertFilterForm').serializeArray().reduce((obj, item) => {
        obj[item.name] = item.value;
        return obj;
    }, {});

    const filterName = $('#filterName').val();
    const filterDescription = $('#filterDescription').val();
    const filterIsPrivate = $('#filterIsPrivate').prop('checked');

    if (!filterName) return;

    const url = '/filters/add';
    post_request_api(url, JSON.stringify({
        filter_name: filterName,
        filter_description: filterDescription,
        filter_data: filterData,
        filter_is_private: filterIsPrivate,
        filter_type: 'alerts',
        csrf_token: $('#csrf_token').val()
    }))
        .then(function (data) {
            if (notify_auto_api(data)) {
                fetchSavedFilters();
            }
        });

    $('#saveFilterModal').modal('hide');
});

function changeStatusAlert(alert_id, status_name) {
    let status_id = getAlertStatusId(status_name);

    let data = {
        'alert_status_id': status_id
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


async function updateAlert(alert_id, data = {}, do_refresh = false, collapse_toggle = false) {
  data['csrf_token'] = $('#csrf_token').val();
  return post_request_api('/alerts/update/' + alert_id, JSON.stringify(data)).then(function (data) {
    if (notify_auto_api(data)) {
      if (do_refresh) {
        const expanded = $(`#additionalDetails-${alert_id}`).hasClass('show');
        return refreshAlert(alert_id, data.data, expanded)
            .then(() => {
                const updatedAlertElement = $(`#alertCard-${alert_id}`);
                if (updatedAlertElement.length) {
                    updatedAlertElement.addClass('fade-it');
                }
            });
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
    if (key === 'filter_id') {
        $('#savedFilters').selectpicker('val', value);
        $('.preset-dropdown-container').show();
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
        if (selectElementId === 'alertOwnerFilter') {
            selectElement.append($('<option>', {
                value: '-1',
                text: 'Unassigned'
            }));
        }

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


async function deleteBatchAlerts(data_content= {}) {
    const selectedAlerts = getBatchAlerts();
    if (selectedAlerts.length === 0) {
        notify_error('Please select at least one alert to perform this action on.');
        return;
    }

    do_deletion_prompt(`You are about to delete ${selectedAlerts.length} alerts`, true)
    .then((doDelete) => {
        if (doDelete) {
            const data = {
                'alert_ids': selectedAlerts,
                'csrf_token': $('#csrf_token').val()
            }

            return post_request_api('/alerts/batch/delete', JSON.stringify(data)).then(
                (data) => {
                    if (notify_auto_api(data)) {
                        setFormValuesFromUrl();
                    }
            });
        }
    });

}

let alertCount = 0;

function updateAlertBadge() {
    const badge = $('#refreshAlertsBadge');

    if (alertCount > 0) {
        badge.text(alertCount).show();
    } else {
        badge.hide();
    }
}

function refreshAlertRelationships(alertId) {
    // Get the checked status of each checkbox
    let fetch_open_alerts = $('input[value="open_alerts"]').is(':checked');
    let fetch_closed_alerts = $('input[value="closed_alerts"]').is(':checked');
    let fetch_open_cases = $('input[value="open_cases"]').is(':checked');
    let fetch_closed_cases = $('input[value="closed_cases"]').is(':checked');

    fetchSimilarAlerts(alertId, true, fetch_open_alerts, fetch_closed_alerts,
        fetch_open_cases, fetch_closed_cases);
}

$(document).ready(function () {
    for (const [selectElementId, configItem] of Object.entries(selectsConfig)) {
        $(`#${selectElementId}`).one('click', function () {
          fetchSelectOptions(selectElementId, configItem)
            .catch(error => console.error(error));
        });
      }

    fetchSavedFilters()
        .then(() => {
            setFormValuesFromUrl();
        });
    getAlertStatusList();

    // Connect to socket.io alerts namespace
    const socket = io.connect('/alerts');

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

    $('#togglePresets').on('click', function() {
        $('.preset-dropdown-container').toggle();
    });

    socket.on('new_alert', function (data) {
        const badge = $('#newAlertsBadge');
        const currentCount = parseInt(badge.text()) || 0;
        badge.text(currentCount + 1).show();
        badge.attr('title', 'New alerts available');
    });

});