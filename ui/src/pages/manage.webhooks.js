// Main function to initialize the DataTable
function initializeDataTable() {
  $("#case_webhooks_table").DataTable({
    ajax: getTableAjaxConfig(),
    order: [[0, "desc"]],
    autoWidth: false,
    columns: getTableColumnsConfig(),
  });
}

// Ajax configuration for DataTable
function getTableAjaxConfig() {
  return {
    url: "/manage/webhooks/list" + case_param(),
    contentType: "application/json",
    type: "GET",
    data: function (d) {
      console.log(d.data);
      if (d.status === "success") {
        return d.data;
      } else {
        return JSON.stringify([]); // Return empty data on failure
      }
    },
  };
}

// Column configuration for DataTable
function getTableColumnsConfig() {
  return [
    { data: "id" },
    { data: "name" },
    {
      data: "payload_schema",
      render: function (data, type, row) {
        return `
          <button type="button" class="btn btn-primary" onclick="handleButtonClick('${row.id}')">
            View Payload
          </button>
        `;
      },
    },
  ];
}

// Function to handle button click for viewing payload details
function handleButtonClick(webhookId) {
  const numericId = parseInt(webhookId, 10);
  console.log(typeof numericId);

  // Fetch webhook details
  const webhookData = fetchWebhookData(numericId);
  if (!webhookData || !webhookData.payload_schema) {
    console.log("No payload schema to display.");
    return;
  }

  // Display payload details
  displayWebhookDetails(webhookData);
}

// Fetch webhook data using AJAX
function fetchWebhookData(id) {
  let webhookData = null;

  $.ajax({
    url: `/manage/webhooks/${id}`,
    contentType: "application/json",
    type: "GET",
    async: false,
    success: function (response) {
      if (response.status === "success") {
        webhookData = response.data;
        console.log(webhookData);
      } else {
        console.log("No data found for this webhook.");
      }
    },
    error: function (xhr, status, error) {
      console.error("Error fetching webhook:", error);
    },
  });

  return webhookData;
}

// Display webhook payload details
function displayWebhookDetails(webhookData) {
  let payloadDetails = `
    <div id="webhook-details">
      <h4>Webhook PayLoad Schema</h4>
      {<ul style="list-style-type: none; padding-left: 0;">
  `;

  for (const [key, value] of Object.entries(webhookData.payload_schema)) {
    payloadDetails += `<li>"${key}": ${JSON.stringify(value, null, 2)}</li>`;
  }

  payloadDetails += `
      </ul>}
      <button class="btn btn-secondary" id="back-to-table">Back</button>
    </div>
  `;

  const container = document.getElementById("drop_case_template_webhooks").querySelector(".card-body");
  container.innerHTML = payloadDetails;
}

// Event handler for "Back" button
$(document).on("click", "#back-to-table", function () {
  restoreTableView();
});

// Restore the table view and reinitialize DataTable
function restoreTableView() {
  const container = document.getElementById("drop_case_template_webhooks").querySelector(".card-body");
  container.innerHTML = `
    <div id="hooks_table_wrapper">
      <table id="case_webhooks_table" class="display" style="width:100%"></table>
    </div>
  `;

  initializeDataTable();
}

// Call to initialize DataTable on script load
initializeDataTable();


function add_webhook() {
  let url = "/manage/webhooks/add/modal" + case_param();
  $("#modal_webhook_json").load(url, function (response, status, xhr) {
    if (status !== "success") {
      ajax_notify_error(xhr, url);
      return false;
    }
    let editor = ace.edit("editor_detail", {
      autoScrollEditorIntoView: true,
      minLines: 30,
    });
    editor.setTheme("ace/theme/tomorrow");
    editor.session.setMode("ace/mode/json");
    editor.renderer.setShowGutter(true);
    editor.setOption("showLineNumbers", true);
    editor.setOption("showPrintMargin", false);
    editor.setOption("displayIndentGuides", true);
    editor.setOption("maxLines", "Infinity");
    editor.session.setUseWrapMode(true);
    editor.setOption("indentedSoftWrap", true);
    editor.renderer.setScrollMargin(8, 5);

    editor.setOptions({
      enableBasicAutocompletion: [
        {
          getCompletions: (editor, session, pos, prefix, callback) => {
            callback(null, [
              { value: "name", score: 1, meta: "name of the webhook" },
              {
                value: "header_auth",
                score: 1,
                meta: "header auth of the webhook",
              },
              {
                value: "payload_schema",
                score: 1,
                meta: "payload of the webhook",
              },
              { value: "url", score: 1, meta: "url of the webhook" },
            ]);
          },
        },
      ],
      enableLiveAutocompletion: true,
      enableSnippets: true,
    });

    $("#submit_new_webhook").on("click", function () {
      let data_sent = Object();
      data_sent["webhook_json"] = editor.getSession().getValue();
      data_sent["csrf_token"] = $("#csrf_token").val();

      post_request_api(
        "/manage/webhooks/add",
        JSON.stringify(data_sent),
        false,
        function () {
          window.swal({
            title: "Adding...",
            text: "Please wait",
            icon: "/static/assets/img/loader.gif",
            button: false,
            allowOutsideClick: false,
          });
        }
      )
        .done((data) => {
          if (notify_auto_api(data)) {
            refresh_webhook_table();
            $("#modal_webhook").modal("hide");
          }
        })
        .fail((error) => {
          let data = error.responseJSON;
          $("#submit_new_webhook").text("Save");
          $("#alert_webhook_edit").text(data.message);
          if (data.data && data.data.length > 0) {
            let output = "<li>" + sanitizeHTML(data.data) + "</li>";
            $("#webhook_err_details_list").append(output);

            $("#alert_webhook_details").show();
          }
          $("#alert_webhook_edit").show();
        })
        .always((data) => {
          window.swal.close();
        });

      return false;
    });
  });
  $("#modal_webhook").modal({ show: true });
}

$("#webhooks_table").dataTable({
  ajax: {
    url: "/manage/webhooks/list" + case_param(),
    contentType: "application/json",
    type: "GET",
    data: function (d) {
      if (d.status == "success") {
        return JSON.stringify(d.data);
      } else {
        return JSON.stringify([]);
      }
    },
  },
  order: [[0, "desc"]],
  autoWidth: false,
  columns: [
    {
      data: "id",
      render: function (data, type, row) {
        return (
          '<a href="#" onclick="webhook_detail(\'' +
          row["id"] +
          "');\">" +
          sanitizeHTML(data) +
          "</a>"
        );
      },
    },
    {
      data: "name",
      render: function (data, type, row) {
        return (
          '<a href="#" onclick="webhook_detail(\'' +
          row["id"] +
          "');\">" +
          sanitizeHTML(data) +
          "</a>"
        );
      },
    },
    {
      data: "url",
    },
  ],
});

function refresh_webhook_table() {
  $("#webhooks_table").DataTable().ajax.reload();
  notify_success("Refreshed");
}

function delete_webhook(id) {
  swal({
    title: "Are you sure ?",
    text: "You won't be able to revert this !",
    icon: "warning",
    buttons: true,
    dangerMode: true,
    confirmButtonColor: "#3085d6",
    cancelButtonColor: "#d33",
    confirmButtonText: "Yes, delete it!",
  }).then((willDelete) => {
    if (willDelete) {
      post_request_api("/manage/webhooks/delete/" + id).done((data) => {
        if (notify_auto_api(data)) {
          window.location.href = "/manage/webhooks" + case_param();
        }
      });
    } else {
      swal("Pfew, that was close");
    }
  });
}

function webhook_detail(ctempl_id) {
  let url = "/manage/webhooks/" + ctempl_id + "/modal" + case_param();
  $("#modal_webhook_json").load(url, function (response, status, xhr) {
    if (status !== "success") {
      ajax_notify_error(xhr, url);
      return false;
    }

    let editor = ace.edit("editor_detail", {
      autoScrollEditorIntoView: true,
      minLines: 30,
    });
    editor.setTheme("ace/theme/tomorrow");
    editor.session.setMode("ace/mode/json");
    editor.renderer.setShowGutter(true);
    editor.setOption("showLineNumbers", true);
    editor.setOption("showPrintMargin", false);
    editor.setOption("displayIndentGuides", true);
    editor.setOption("maxLines", "Infinity");
    editor.session.setUseWrapMode(true);
    editor.setOption("indentedSoftWrap", true);
    editor.renderer.setScrollMargin(8, 5);

    editor.setOptions({
      enableBasicAutocompletion: [
        {
          getCompletions: (editor, session, pos, prefix, callback) => {
            callback(null, [
              { value: "name", score: 1, meta: "name of the webhook" },
              {
                value: "header_auth",
                score: 1,
                meta: "header auth of the webhook",
              },
              {
                value: "payload_schema",
                score: 1,
                meta: "payload of the webhook",
              },
              { value: "url", score: 1, meta: "url of the webhook" },
            ]);
          },
        },
      ],
      enableLiveAutocompletion: true,
      enableSnippets: true,
    });

    $("#submit_new_webhook").on("click", function () {
      update_webhook(ctempl_id, editor, false, false);
    });

    $("#submit_delete_webhook").on("click", function () {
      delete_webhook(ctempl_id);
    });
  });
  $("#modal_webhook").modal({ show: true });
}

function update_webhook(ctempl_id, editor, partial, complete) {
  event.preventDefault();

  let data_sent = Object();
  data_sent["webhook_json"] = editor.getSession().getValue();
  data_sent["csrf_token"] = $("#csrf_token").val();

  $("#alert_webhook_edit").empty();
  $("#alert_webhook_details").hide();
  $("#webhook_err_details_list").empty();

  post_request_api(
    "/manage/webhooks/update/" + ctempl_id,
    JSON.stringify(data_sent),
    false,
    function () {
      window.swal({
        title: "Updating...",
        text: "Please wait",
        icon: "/static/assets/img/loader.gif",
        button: false,
        allowOutsideClick: false,
      });
    }
  )
    .done((data) => {
      notify_auto_api(data);
    })
    .fail((error) => {
      let data = error.responseJSON;
      $("#submit_webhook_template").text("Update");
      $("#alert_webhook_edit").text(data.message);
      if (data.data && data.data.length > 0) {
        let output = "<li>" + sanitizeHTML(data.data) + "</li>";
        $("#webhook_err_details_list").append(output);

        $("#alert_webhook_details").show();
      }
      $("#alert_webhook_edit").show();
    })
    .always((data) => {
      window.swal.close();
    });

  return false;
}

function fire_upload_webhook() {
  let url = "/manage/webhooks/upload/modal" + case_param();
  $("#modal_upload_webhook_json").load(url, function (response, status, xhr) {
    if (status !== "success") {
      ajax_notify_error(xhr, url);
      return false;
    }
  });
  $("#modal_upload_webhook").modal({ show: true });
}

function upload_webhook() {
  if ($("#input_upload_webhook").val() !== "") {
    var file = $("#input_upload_webhook").get(0).files[0];
    var reader = new FileReader();
    reader.onload = function (e) {
      fileData = e.target.result;
      var data = new Object();
      data["csrf_token"] = $("#csrf_token").val();
      data["webhook_json"] = fileData;

      post_request_api(
        "/manage/webhooks/add",
        JSON.stringify(data),
        false,
        function () {
          window.swal({
            title: "Adding...",
            text: "Please wait",
            icon: "/static/assets/img/loader.gif",
            button: false,
            allowOutsideClick: false,
          });
        }
      )
        .done((data) => {
          notify_auto_api(data);
          jsdata = data;
          if (jsdata.status == "success") {
            refresh_webhook_table();
            $("#modal_upload_webhook").modal("hide");
          }
        })
        .fail((error) => {
          let data = error.responseJSON;
          $("#alert_upload_webhook").text(data.message);
          if (data.data && data.data.length > 0) {
            let output = "<li>" + sanitizeHTML(data.data) + "</li>";
            $("#upload_webhook_err_details_list").append(output);

            $("#alert_upload_webhook_details").show();
          }
          $("#alert_upload_webhook").show();
        })
        .always((data) => {
          $("#input_upload_webhook").val("");
          window.swal.close();
        });
    };
    reader.readAsText(file);
  }

  return false;
}

function downloadwebhookDefinition() {
  event.preventDefault();
  let editor = ace.edit("editor_detail");
  let data = editor.getSession().getValue();

  let filename = "webhook.json";
  download_file(filename, "text/json", data);
}
