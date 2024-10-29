/* reload the asset table */
g_asset_id = null;
g_asset_desc_editor = null;


function reload_assets() {
    get_case_assets();
}

function edit_in_asset_desc() {

    if($('#container_asset_desc_content').is(':visible')) {
        $('#container_asset_description').show(100);
        $('#container_asset_desc_content').hide(100);
        $('#asset_edition_btn').hide(100);
        $('#asset_preview_button').hide(100);
    } else {
        $('#asset_preview_button').show(100);
        $('#asset_edition_btn').show(100);
        $('#container_asset_desc_content').show(100);
        $('#container_asset_description').hide(100);
    }
}

/* Fetch a modal that is compatible with the requested asset type */
function add_assets() {
    url = 'assets/add/modal' + case_param();
    $('#modal_add_asset_content').load(url, function (response, status, xhr) {
        hide_minimized_modal_box();
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        g_asset_desc_editor = get_new_ace_editor('asset_description', 'asset_desc_content', 'target_asset_desc',
                            function() {
                                $('#last_saved').addClass('btn-danger').removeClass('btn-success');
                                $('#last_saved > i').attr('class', "fa-solid fa-file-circle-exclamation");
                            }, null);
        g_asset_desc_editor.setOption("minLines", "10");
        edit_in_asset_desc();

        let headers = get_editor_headers('g_asset_desc_editor', null, 'asset_edition_btn');
        $('#asset_edition_btn').append(headers);

        $('#ioc_links').select2({});

        $('#submit_new_assets').on("click", function () {

            let assets = $('#assets_name').val();
            let assets_list = assets.split('\n');
            for (let index in assets_list) {

                let data = $('#form_new_assets').serializeObject();
                data['asset_name'] = assets_list[index];
                delete data['assets_name'];

                if (data['asset_name'] == "" || data['asset_name'] == null || data['asset_name'] == '\n') {
                    continue;
                }

                data['csrf_token'] = $('#csrf_token').val();
                if (typeof data["ioc_links"] == "string") {
                    data["ioc_links"] = [data["ioc_links"]]
                }
                data['asset_tags'] = $('#asset_tags').val();
                data['asset_description'] = g_asset_desc_editor.getValue();
                let ret = get_custom_attributes_fields();
                let has_error = ret[0].length > 0;
                let attributes = ret[1];

                if (has_error) {
                    return false;
                }

                data['custom_attributes'] = attributes;

                post_request_api('assets/add', JSON.stringify(data), true, function () {
                    $('#submit_new_assets').text('Saving data..')
                        .attr("disabled", true)
                        .removeClass('bt-outline-success')
                        .addClass('btn-success', 'text-dark');
                })
                    .done((data) => {
                        if (data.status == 'success') {
                            reload_assets();
                            if (index == (assets_list.length - 1)) {
                                $('#modal_add_asset').modal('hide');
                                notify_success("Assets created");
                            }
                        } else {
                            $('#submit_new_assets').text('Save again');
                            swal("Oh no !", data.message, "error")
                        }
                    })
                    .always(function () {
                        $('#submit_new_assets')
                            .attr("disabled", false)
                            .addClass('bt-outline-success')
                            .removeClass('btn-success', 'text-dark');
                    })
                    .fail(function (error) {
                        $('#submit_new_assets').text('Save');
                        propagate_form_api_errors(error.responseJSON.data);
                    })
            }

            return false;
        })

        $('#modal_add_asset').modal({ show: true });
        $('#asset_name').focus();

    });

    $('.dtr-modal').hide();
}

/* Retrieve the list of assets and build a datatable for each type of asset */
function get_case_assets() {
    show_loader();

    get_request_api('/case/assets/filter')
    .done(function (response) {
        if (response.status == 'success') {
            if (response.data != null) {
                jsdata = response.data;
                if (jsdata.assets.length > 299) {
                    set_page_warning("Backref disabled due to too many assets in the case");
                } else {
                    set_page_warning("");
                }
                Table.clear();
                Table.rows.add(jsdata.assets);
                Table.columns.adjust().draw();
                load_menu_mod_options('asset', Table, delete_asset, [{
                    type: 'option',
                    title: 'Check Alerts',
                    multi: false,
                    iconClass: 'fas fa-bell',
                    action: function(rows) {
                        let row = rows[0];
                        let asset = get_row_value(row);
                        window.open(`/alerts?alert_assets=${asset}`, '_blank');
                    }
                }]);
                $('[data-toggle="popover"]').popover();
                set_last_state(jsdata.state);
                hide_loader();
                Table.responsive.recalc();

                $(document)
                    .off('click', '.asset_details_link')
                    .on('click', '.asset_details_link', function(event) {
                    event.preventDefault();
                    let asset_id = $(this).data('asset_id');
                    asset_details(asset_id);
                });

            } else {
                Table.clear().draw();
                swal("Oh no !", data.message, "error")
            }
        } else {
            Table.clear().draw()
        }
    })
}

/* Delete an asset */
function delete_asset(asset_id) {
    do_deletion_prompt("You are about to delete asset #" + asset_id)
    .then((doDelete) => {
        if (doDelete) {
            post_request_api('assets/delete/' + asset_id)
            .done((data) => {
                if (data.status == 'success') {
                    reload_assets();
                    $('#modal_add_asset').modal('hide');
                    notify_success('Asset deleted');
                } else {
                    swal("Oh no !", data.message, "error")
                }
            });
        }
    });
}

/* Fetch the details of an asset and allow modification */
function asset_details(asset_id) {

    url = 'assets/' + asset_id + '/modal' + case_param();
    $('#modal_add_asset_content').load(url, function (response, status, xhr) {
        hide_minimized_modal_box();
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        g_asset_id = asset_id;
        g_asset_desc_editor = get_new_ace_editor('asset_description', 'asset_desc_content', 'target_asset_desc',
                            function() {
                                $('#last_saved').addClass('btn-danger').removeClass('btn-success');
                                $('#last_saved > i').attr('class', "fa-solid fa-file-circle-exclamation");
                            }, null, false, false);

        g_asset_desc_editor.setOption("minLines", "10");
        preview_asset_description(true);
        headers = get_editor_headers('g_asset_desc_editor', null, 'asset_edition_btn');

        $('#asset_edition_btn').append(headers);

        $('#ioc_links').select2({});


        $('#submit_new_asset').on("click", function () {
            update_asset(true);
            return false;
        })

        load_menu_mod_options_modal(asset_id, 'asset', $("#asset_modal_quick_actions"));
        $('.dtr-modal').hide();

        $('#modal_add_asset').modal({ show: true });
        edit_in_asset_desc();
    });


    return false;
}

function preview_asset_description(no_btn_update) {
    if(!$('#container_asset_description').is(':visible')) {
        asset_desc = g_asset_desc_editor.getValue();
        converter = get_showdown_convert();
        html = converter.makeHtml(do_md_filter_xss(asset_desc));
        asset_desc_html = do_md_filter_xss(html);
        $('#target_asset_desc').html(asset_desc_html);
        $('#container_asset_description').show();
        if (!no_btn_update) {
            $('#asset_preview_button').html('<i class="fa-solid fa-eye-slash"></i>');
        }
        $('#container_asset_desc_content').hide();
    }
    else {
        $('#container_asset_description').hide();
         if (!no_btn_update) {
            $('#asset_preview_button').html('<i class="fa-solid fa-eye"></i>');
        }

        $('#asset_preview_button').html('<i class="fa-solid fa-eye"></i>');
        $('#container_asset_desc_content').show();
    }
}


function save_asset(){
    $('#submit_new_asset').click();
}

function update_asset(do_close){
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
    data['asset_description'] = g_asset_desc_editor.getValue();

    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}

    data['custom_attributes'] = attributes;

    post_request_api('assets/update/' + g_asset_id, JSON.stringify(data),  true)
    .done((data) => {
        if (data.status == 'success') {
            reload_assets();
            $('#submit_new_asset').text("Saved").addClass('btn-outline-success').removeClass('btn-outline-danger').removeClass('btn-outline-warning');
            $('#last_saved').removeClass('btn-danger').addClass('btn-success');
            $('#last_saved > i').attr('class', "fa-solid fa-file-circle-check");
            if (do_close) {
                $('#modal_add_asset').modal('hide');
            }
            notify_success('Asset updated');
        } else {
            $('#submit_new_asset').text('Save again');
            swal("Oh no !", data.message, "error")
        }
    })

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

        post_request_api('/case/assets/upload', JSON.stringify(data), true)
        .done((data) => {
            jsdata = data;
            if (jsdata.status == "success") {
                reload_assets();
                $('#modal_upload_assets').modal('hide');
                swal("Got news for you", data.message, "success");

            } else {
                swal("Got bad news for you", data.message, "error");
            }
        })

    };
    reader.readAsText(file)

    return false;
}

function generate_sample_csv(){
    csv_data = "asset_name,asset_type_name,asset_description,asset_ip,asset_domain,asset_tags\n"
    csv_data += '"My computer","Mac - Computer","Computer of Mme Michu","192.168.15.5","iris.local","Compta|Mac"\n'
    csv_data += '"XCAS","Windows - Server","Xcas server","192.168.15.48","iris.local",""'
    download_file("sample_assets.csv", "text/csv", csv_data);
}

/* Page is ready, fetch the assets of the case */
$(document).ready(function(){

    /* add filtering fields for each table of the page (must be done before datatable initialization) */
    $.each($.find("table"), function(index, element){
        addFilterFields($(element).attr("id"));
    });

    Table = $("#assets_table").DataTable({
        dom: '<"container-fluid"<"row"<"col"l><"col"f>>>rt<"container-fluid"<"row"<"col"i><"col"p>>>',
        aaData: [],
        aoColumns: [
          {
            "data": "asset_name",
            "className": "dt-nowrap",
            "render": function (data, type, row, meta) {
                  if (type === 'display' || type === 'filter' || type === 'sort' || type === 'export') {

                    // Create container element
                    const container = document.createElement('div');

                    let datak = "";
                    if (row['asset_domain']) {
                        datak = row['asset_domain'] + "\\" + data;
                    } else {
                        datak = data;
                    }
                    if (data.length > 60) {
                        datak = data.slice(0, 60) + " (..)";
                    }
                    if (isWhiteSpace(data)) {
                        datak = '#' + row['asset_id'];
                    }

                    let compro = "";

                    if (row.link.length > 0) {
                        let has_compro = false;
                        let datacontent = 'data-content="';

                        row.link.forEach(link => {
                            const caseInfo = `<b><a target='_blank' rel='noopener' href='/case/assets?cid=${link.case_id}&shared=${link.asset_id}'>Observed <sup><i class='fa-solid fa-arrow-up-right-from-square ml-1 mr-1 text-muted'></i></sup></a></b>`;
                            const caseLink = `<b><a href='/case?cid=${link.case_id}'>case #${link.case_id} <sup><i class='fa-solid fa-arrow-up-right-from-square ml-1 mr-1 text-muted'></i></sup></a></b>`;
                            const date = link.case_open_date.replace('00:00:00 GMT', '');

                            if (link.asset_compromise_status_id === 1) {
                                has_compro = true;
                                datacontent += `${caseInfo} as <b class='text-danger'>compromised</b><br/> on ${caseLink} (${date}) for the same customer.<br/><br/>`;
                            } else {
                                datacontent += `${caseInfo} as <b class='text-success'>not compromised</b><br/> on ${caseLink} (${date}) for the same customer.<br/><br/>`;
                            }
                        });

                        compro += `<i tabindex="0" class="fas ${has_compro ? 'fa-meteor text-danger' : 'fa-info-circle text-success'} ml-2" style="cursor: pointer;" data-html="true" data-toggle="popover" data-trigger="focus" title="Observed in previous case" ${datacontent}"></i>`;
                    }

                    if (row.alerts.length > 0) {
                        let alerts_content = "";

                        row.alerts.forEach(alert => {
                            alerts_content += `<i tabindex="0" class="fas fa-bell text-warning mr-2"></i><a href=\"/alerts?alert_ids=${alert.alert_id}&page=1&per_page=1&sort=desc\" target="_blank" rel="noopener">#${alert.alert_id} - ${alert.alert_title.replace(/'/g, "&#39;").replace(/"/g, "&quot;")}</a><br/>`;
                        }  );
                        alerts_content += `<i tabindex="0" class="fas fa-external-link-square mr-2"></i><a href=\"/alerts?alert_assets=${data}" target="_blank" rel="noopener">More..</a>`;


                        compro += `<i tabindex="0" class="fas fa-bell text-warning ml-2" style="cursor: pointer;" data-html="true" data-toggle="popover" data-trigger="focus" title="Alerts" data-content='${alerts_content}'></i>`;
                    }

                    let img = $('<img>')
                        .addClass('mr-2')
                        .css({width: '1.5em', height: '1.5em'})
                        .attr('src', '/static/assets/img/graph/' + (row['asset_compromise_status_id'] == 1 ? row['asset_type']['asset_icon_compromised'] : row['asset_type']['asset_icon_not_compromised']))
                        .attr('title', row['asset_type']['asset_name']);

                    let link = $('<a>')
                        .attr('href', 'javascript:void(0);')
                        .attr('data-asset_id', row['asset_id'])
                        .attr('title', 'Asset ID #' + row['asset_id'])
                        .addClass('asset_details_link')
                        .text(datak);

                    let con = $('<div>').append(img, link);

                    return con.html() + compro;
                }
                return data;
            }
          },
          {
            "data": "asset_type.asset_name",
             "render": function (data, type, row, meta) {
                if (type === 'display') { data = sanitizeHTML(data);}
                return data;
              }
          },
          { "data": "asset_description",
           "render": function (data, type, row, meta) {
              if (type === 'display' && data != null) {
                  return ret_obj_dt_description(data);
              }
              return data;
            }
          },
          { "data": "asset_ip",
             "render": function (data, type, row, meta) {
                if (type === 'display'  && data != null) {
                    return ret_obj_dt_description(data);
                }
                return data;
              }
          },
          { "data": "asset_compromise_status_id",
           "render": function(data, type, row) {
                if (data == 0) { ret = '<span class="badge badge-muted">TBD</span>';}
                else if (data == 1) { ret = '<span class="badge badge-danger">Yes</span>';}
                else if (data == 2) { ret = '<span class="badge badge-success">No</span>';}
                else { ret = '<span class="badge badge-warning">Unknown</span>';}
                return ret;
            }
          },
        {
            "data": "ioc_links",
            "render": function (data, type, row, meta) {
                if ((type === 'filter' || type === 'display') && data != null) {
                    let datas = "";
                    for (ds in data) {
                        datas += get_ioc_tag_from_data(data[ds]['ioc_value'], 'badge badge-light ml-2');
                    }
                    return datas;
                } else if (type === 'export' && data != null) {
                    let datas = data.map(ds => sanitizeHTML(ds['ioc_value'])).join(',');
                    return datas;
                }
                return data;
            }
        },
          { "data": "asset_tags",
            "render": function (data, type, row, meta) {
              if (type === 'display' && data != null  ) {
                  let tags = "";
                  let de = data.split(',');
                  for (let tag in de) {
                      tags += get_tag_from_data(de[tag], 'badge badge-light ml-2');
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
                data = sanitizeHTML(data['name']);
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
                    display: $.fn.dataTable.Responsive.display.childRow,
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
            tableFiltering(this.api(), 'assets_table');
        },
        select: true
    });
    $("#assets_table").css("font-size", 12);

    Table.on( 'responsive-resize', function ( e, datatable, columns ) {
            hide_table_search_input( columns );
    });

    var buttons = new $.fn.dataTable.Buttons(Table, {
     buttons: [
        { "extend": 'csvHtml5', "text":'<i class="fas fa-cloud-download-alt"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Download as CSV', "exportOptions": { "columns": ':visible', 'orthogonal':  'export' } } ,
        { "extend": 'copyHtml5', "text":'<i class="fas fa-copy"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Copy', "exportOptions": { "columns": ':visible', 'orthogonal':  'export' } },
        { "extend": 'colvis', "text":'<i class="fas fa-eye-slash"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Toggle columns' }
    ]
    }).container().appendTo($('#tables_button'));

    get_case_assets();
    setInterval(function() { check_update('assets/state'); }, 3000);

    shared_id = getSharedLink();
    if (shared_id) {
        asset_details(shared_id);
    }
});