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

Table = $("#assets_table").DataTable({
    dom: 'Blfrtip',
    aaData: [],
    aoColumns: [
      {
        "data": "asset_name",
        "render": function (data, type, row, meta) {
          if (type === 'display') {
            datak= sanitizeHTML(data);

            if (data.length > 60) {
                datak = data.slice(0, 60) + " (..)";
            }
            if (isWhiteSpace(data)) {
                datak = '#' + row['asset_id'];
            }
            ret = '<a href="#"  onclick="asset_details(\'' + row['asset_id'] + '\');">' + datak +'</a>';

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
                        data-toggle="popover" data-trigger="focus" title="Observed on previous case" `;
                } else {
                    ret += `<i class="fas fa-info-circle ml-2 text-success" style="cursor: pointer;" data-html="true"
                    data-toggle="popover" data-trigger="focus" title="Observed on previous case" `;
                }

                ret += datacontent;
                ret += '"></i>';
            }
            return ret;
          }
          return data;
        }
      },
      { "data": "asset_compromised",
       "render": function(data, type, row) {
            if (data == true) { ret = '<span class="badge badge-danger">Yes</span>';} else { ret = '<span class="badge badge-success">No</span>'}
            return ret;
        }
      },
      { "data": "asset_description",
       "render": function (data, type, row, meta) {
          if (type === 'display' && data != null) {
            data = sanitizeHTML(data);
            datas = '<span data-toggle="popover" style="cursor: pointer;" title="Info" data-trigger="focus" href="#" data-content="' + data + '">' + data.slice(0, 70);

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
      { "data": "ioc",
        "render": function (data, type, row, meta) {
          if (type === 'display' && data != undefined) {
            datas = "";
            for (ds in data) {
                datas += '<span class="badge badge-light">'+ sanitizeHTML(data[ds][0]) + '</span>';
            }
            return datas;
          }
          return data;
        }
      },
      { "data": "asset_ip"
      },
      {
        "data": "asset_type"
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
    "language": {
                    "processing": '<i class="fa fa-spinner fa-spin" style="font-size:24px;color:rgb(75, 183, 245);"></i>'
                 },
    retrieve: true,
    buttons: []
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
            if (typeof data["ioc_links"] == "string") {
                data["ioc_links"] = [data["ioc_links"]]
            }

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


    });
    $('#modal_add_asset').modal({ show: true });
}


/* Page is ready, fetch the assets of the case */
$(document).ready(function(){
    get_case_assets();
    setInterval(function() { check_update('assets/state'); }, 3000);
});
