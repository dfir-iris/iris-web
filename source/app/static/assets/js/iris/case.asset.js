/* reload the asset table */
function reload_assets() {
    get_case_assets();
}

/* Fetch a modal that is compatible with the requested asset type */
function add_asset() {
    url = 'assets/add/modal' + case_param();
    $('#modal_add_asset_content').load(url, function () {

        $('#ioc_links').select2({});

        $('#submit_new_asset').on("click", function () {
            if(!$('form#form_new_asset').valid()) {
                return false;
            }

            var data = $('#form_new_asset').serializeObject();
            data['csrf_token'] = $('#csrf_token').val();
            if (typeof data["ioc_links"] == "string") {
                data["ioc_links"] = [data["ioc_links"]]
            }
            data['asset_tags'] = $('#asset_tags').val();
            ret = get_custom_attributes_fields();
            has_error = ret[0].length > 0;
            attributes = ret[1];

            if (has_error){return false;}

            data['custom_attributes'] = attributes;

            $.ajax({
                url: 'assets/add' + case_param(),
                type: "POST",
                data: JSON.stringify(data),
                contentType: "application/json;charset=UTF-8",
                dataType: "json",
                beforeSend: function () {
                    $('#submit_new_asset').text('Saving data..')
                        .attr("disabled", true)
                        .removeClass('bt-outline-success')
                        .addClass('btn-success', 'text-dark');
                },
                complete: function () {
                    $('#submit_new_asset')
                        .attr("disabled", false)
                        .addClass('bt-outline-success')
                        .removeClass('btn-success', 'text-dark');
                },
                success: function (data) {
                    if (data.status == 'success') {
                        swal("Done !",
                        "Your asset has been created successfully",
                            {
                                icon: "success",
                                timer: 500
                            }
                        ).then((value) => {
                            reload_assets();
                            $('#modal_add_asset').modal('hide');

                        });
                    } else {
                        $('#submit_new_asset').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    $('#submit_new_asset').text('Save');
                    propagate_form_api_errors(error.responseJSON.data);
                }
            });

            return false;
        })
    });
    $('#modal_add_asset').modal({ show: true });
}

/* add filtering fields for each table of the page (must be done before datatable initialization) */
$.each($.find("table"), function(index, element){
    addFilterFields($(element).attr("id"));
});

Table = $("#assets_table").DataTable({
    dom: 'Blfrtip',
    aaData: [],
    aoColumns: [
      {
        "data": "asset_name",
        "render": function (data, type, row, meta) {
          if (type === 'display') {
            if (row['asset_domain']) {
                datak = sanitizeHTML(row['asset_domain'])+"\\"+ sanitizeHTML(data);
            } else {
                datak = sanitizeHTML(data);
            }

            if (data.length > 60) {
                datak = data.slice(0, 60) + " (..)";
            }
            if (isWhiteSpace(data)) {
                datak = '#' + row['asset_id'];
            }
            share_link = buildShareLink(row['asset_id']);
            if (row['asset_compromised']) {
                src_icon = row['asset_icon_compromised'];
            } else {
                src_icon = row['asset_icon_not_compromised'];
            }
            ret = '<img class="mr-2" title="'+ sanitizeHTML(row['asset_type']) +'" style="width:2em;height:2em" src=\'/static/assets/img/graph/' + src_icon +
            '\'> <a href="' + share_link + '" data-selector="true" title="Asset ID #'+ row['asset_id'] +
            '" onclick="asset_details(\'' + row['asset_id'] + '\');return false;">' + datak +'</a>';

            if (row.link.length > 0) {
                var has_compro = false;
                var datacontent = 'data-content="';
                for (idx in row.link) {
                    if (row.link[idx]['asset_compromised']) {
                        has_compro = true;
                        datacontent += `Observed as <b class=\'text-danger\'>compromised</b><br/>
                        on investigation <b>`+ sanitizeHTML(row.link[idx]['case_name']) + `</b> (open on `+ row.link[idx]['case_open_date'].replace('00:00:00 GMT', '') +`) for the same customer.
                        <br/><b>Asset description</b> :` + sanitizeHTML(row.link[idx]['asset_description']) + "<br/><br/>";
                    } else {

                        datacontent += `Observed as <b class=\'text-success\'>not compromised</b><br/>
                        on investigation <b>`+ sanitizeHTML(row.link[idx]['case_name']) + `</b> (open on `+ row.link[idx]['case_open_date'].replace('00:00:00 GMT', '') +`) for the same customer.
                        <br/><b>Asset description</b> :` + sanitizeHTML(row.link[idx]['asset_description']) + "<br/><br/>";
                    }
                }
                if (has_compro) {
                   ret += `<i class="fas fa-skull ml-2 text-danger" style="cursor: pointer;" data-html="true"
                        data-toggle="popover" data-trigger="hover" title="Observed on previous case" `;
                } else {
                    ret += `<i class="fas fa-info-circle ml-2 text-success" style="cursor: pointer;" data-html="true"
                    data-toggle="popover" data-trigger="hover" title="Observed on previous case" `;
                }

                ret += datacontent;
                ret += '"></i>';
            }
            return ret;
          }
          return data;
        }
      },
      {
        "data": "asset_type",
         "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
      },
      { "data": "asset_description",
       "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
            data = sanitizeHTML(data);
            datas = '<span data-toggle="popover" style="cursor: pointer;" title="Info" data-trigger="hover" href="#" data-content="' + data + '">' + data.slice(0, 70);

            if (data.length > 70) {
                datas += ' (..)</span>';
            } else {
                datas += '</span>';
            }
            return datas;
          }
          return data;
        }
      },
      { "data": "asset_ip",
         "render": function (data, type, row, meta) {
            if (type === 'display') { data = sanitizeHTML(data);}
            return data;
          }
      },
      { "data": "asset_compromised",
       "render": function(data, type, row) {
            if (data == true) { ret = '<span class="badge badge-danger">Yes</span>';} else { ret = '<span class="badge badge-success">No</span>'}
            return ret;
        }
      },
      { "data": "ioc_links",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
            datas = "";
            for (ds in data) {
                datas += '<span class="badge badge-light">'+ sanitizeHTML(data[ds]['ioc_value']) + '</span>';
            }
            return datas;
          }
          return data;
        }
      },
      { "data": "asset_tags",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
              tags = "";
              de = data.split(',');
              for (tag in de) {
                tags += '<span class="badge badge-light ml-2">' + sanitizeHTML(de[tag]) + '</span>';
              }
              return tags;
          }
          return data;
        }
      },
      {
        "data": "analysis_status",
        "render": function(data, type, row, meta) {
           if (type === 'display') {
            data = sanitizeHTML(data);
            if (data == 'To be done') {
                flag = 'danger';
            } else if (data == 'Started') {
                flag = 'warning';
            } else if (data == 'Done') {
                flag = 'success';
            } else {
                flag = 'muted';
            }
              data = '<span class="badge ml-2 badge-'+ flag +'">' + data + '</span>';
          }
          return data;
        }
      }
    ],
    filter: true,
    info: true,
    ordering: true,
    processing: true,
    responsive: {
            details: {
                display: $.fn.dataTable.Responsive.display.modal( {
                    header: function ( row ) {
                        var data = row.data();
                        return 'Details for '+data[0]+' '+data[1];
                    }
                } ),
                renderer: $.fn.dataTable.Responsive.renderer.tableAll()
            }
    },
    language: {
        "processing": '<i class="fa fa-spinner fa-spin" style="font-size:24px;color:rgb(75, 183, 245);"></i>'
    },
    retrieve: true,
    buttons: [],
    orderCellsTop: true,
    initComplete: function () {
        tableFiltering(this.api());
    },
    select: true
});
$("#assets_table").css("font-size", 12);

var buttons = new $.fn.dataTable.Buttons(Table, {
     buttons: [
        { "extend": 'csvHtml5', "text":'<i class="fas fa-cloud-download-alt"></i>',"className": 'btn btn-link text-white pl--2'
        , "titleAttr": 'Download as CSV' },
        { "extend": 'copyHtml5', "text":'<i class="fas fa-copy"></i>',"className": 'btn btn-link text-white pl--2'
        , "titleAttr": 'Copy' },
    ]
}).container().appendTo($('#tables_button'));

Table.on( 'responsive-resize', function ( e, datatable, columns ) {
        hideSearchInputs( columns );
});

/* Retrieve the list of assets and build a datatable for each type of asset */
function get_case_assets() {
    show_loader();
    $.ajax({
        url: "/case/assets/list" + case_param(),
        type: "GET",
        dataType: 'json',
        success: function (response) {
            if (response.status == 'success') {
                if (response.data != null) {
                    jsdata = response.data;
                    Table.clear();
                    Table.rows.add(jsdata.assets);
                    Table.columns.adjust().draw();
                    load_menu_mod_options('asset', Table);

                    set_last_state(jsdata.state);
                    hide_loader();
                    $('#assets_table').on('click', function(e){
                        if($('.popover-link').length>1)
                            $('.popover-link').popover('hide');
                            $(e.target).popover('toggle');
                        });

                } else {
                    Table.clear().draw();
                    swal("Oh no !", data.message, "error")
                }
            } else {
                Table.clear().draw()
            }
        },
        error: function (error) {
            swal("Oh no !", error.statusText, "error")
        }
    });
}

/* Delete an asset */
function delete_asset(asset_id) {
    $.ajax({
        url: 'assets/delete/' + asset_id + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                swal("Good !",
                    "The asset has been deleted successfully",
                    {
                        icon: "success",
                        timer: 500
                    }
                ).then((value) => {
                    reload_assets();
                    $('#modal_add_asset').modal('hide');
                });

            } else {
                swal("Oh no !", data.message, "error")
            }
        },
        error: function (error) {
            swal("Oh no !", error.statusText, "error")
        }
    });
}



/* Fetch the details of an asset and allow modification */
function asset_details(asset_id) {

    url = 'assets/' + asset_id + '/modal' + case_param();
    $('#modal_add_asset_content').load(url, function () {

        $('#ioc_links').select2({});


        $('#submit_new_asset').on("click", function () {
            if(!$('form#form_new_asset').valid()) {
                return false;
            }

            var data = $('#form_new_asset').serializeObject();
            if (typeof data["ioc_links"] === "string") {
                data["ioc_links"] = [data["ioc_links"]]
            } else if (typeof data["ioc_links"] === "object") {
                tmp_data = [];
                for (ioc_link in data["ioc_links"]) {
                    if (typeof ioc_link === "string") {
                        tmp_data.push(data["ioc_links"][ioc_link]);
                    }
                }
                data["ioc_links"] = tmp_data;
            }
            else {
                data["ioc_links"] = [];
            }
            data['asset_tags'] = $('#asset_tags').val();
            if (!data.hasOwnProperty('asset_compromised')) {
                data['asset_compromised'] = 'false';
            }

            ret = get_custom_attributes_fields();
            has_error = ret[0].length > 0;
            attributes = ret[1];

            if (has_error){return false;}

            data['custom_attributes'] = attributes;

            $.ajax({
                url: 'assets/update/' + asset_id + case_param(),
                type: "POST",
                data: JSON.stringify(data),
                dataType: "json",
                contentType: "application/json;charset=UTF-8",
                success: function (data) {
                    if (data.status == 'success') {
                        swal("You're set !",
                            "The asset has been updated successfully",
                            {
                                icon: "success",
                                timer: 500
                            }
                        ).then((value) => {
                            reload_assets();
                            $('#modal_add_asset').modal('hide');
                        });

                    } else {
                        $('#submit_new_asset').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                   propagate_form_api_errors(error.responseJSON.data);
                }
            });

            return false;
        })

        load_menu_mod_options_modal(asset_id, 'asset', $("#asset_modal_quick_actions"));
    });
    $('#modal_add_asset').modal({ show: true });
    return false;
}

function fire_upload_assets() {
    $('#modal_upload_assets').modal('show');
}


function upload_assets() {

    var file = $("#input_upload_assets").get(0).files[0];
    var reader = new FileReader();
    reader.onload = function (e) {
        fileData = e.target.result
        var data = new Object();
        data['csrf_token'] = $('#csrf_token').val();
        data['CSVData'] = fileData;
        $.ajax({
            url: '/case/assets/upload' + case_param(),
            type: "POST",
            data: JSON.stringify(data),
            contentType: "application/json;charset=UTF-8",
            dataType: "json",
            success: function (data) {
                jsdata = data;
                if (jsdata.status == "success") {
                    reload_assets();
                    $('#modal_upload_assets').modal('hide');
                    swal("Got news for you", data.message, "success");

                } else {
                    swal("Got bad news for you", data.message, "error");
                }
            },
            error: function (error) {
                notify_error(error.responseJSON.message);
                propagate_form_api_errors(error.responseJSON.data);
            }
        });
    };
    reader.readAsText(file)

    return false;
}

  function hideSearchInputs(columns) {
    for (i=0; i<columns.length; i++) {
      if (columns[i]) {
        $('.filters th:eq(' + i + ')' ).show();
      } else {
        $('.filters th:eq(' + i + ')' ).hide();
      }
    }
  }

function generate_sample_csv(){
    csv_data = "asset_name,asset_type_name,asset_description,asset_ip,asset_domain,asset_tags\n"
    csv_data += '"My computer","Mac - Computer","Computer of Mme Michu","192.168.15.5","iris.local","Compta|Mac"\n'
    csv_data += '"XCAS","Windows - Server","Xcas server","192.168.15.48","iris.local",""'
    download_file("sample_assets.csv", "text/csv", csv_data);
}


function download_file(filename, contentType, data) {
    var element = document.createElement('a');
    element.setAttribute('href', 'data:' + contentType + ';charset=utf-8,' + encodeURIComponent(data));
    element.setAttribute('download', filename);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
}


/* Page is ready, fetch the assets of the case */
$(document).ready(function(){
    get_case_assets();
    setInterval(function() { check_update('assets/state'); }, 3000);

    shared_id = getSharedLink();
    if (shared_id) {
        asset_details(shared_id);
    }
});