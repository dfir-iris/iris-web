/* Fetch a modal that allows to add an event */ 
function add_event() {
    url = 'timeline/event/add/modal' + case_param();
    $('#modal_add_event_content').load(url, function () {   
        $('#submit_new_event').on("click", function () {
            clear_api_error();
            var data_sent = $('#form_new_event').serializeObject();
            data_sent['event_date'] = $('#event_date').val();
            data_sent['event_time'] = $('#event_time').val();
            data_sent['event_in_summary'] = $('#event_in_summary').is(':checked');
            data_sent['event_in_graph'] = $('#event_in_graph').is(':checked');
            data_sent['event_tags'] = $('#event_tags').val();
            data_sent['event_assets'] = $('#event_assets').val();
            data_sent['event_tz'] = $('#event_tz').val();

            $.ajax({
                url: 'timeline/event/add' + case_param(),
                type: "POST",
                data: JSON.stringify(data_sent),
                contentType: "application/json;charset=UTF-8",
                dataType: "json",
                success: function (data) {
                    if (data.status == 'success') {
                        swal("Done !",
                        "Your event has been created successfully",
                            {
                                icon: "success",
                                timer: 400
                            }
                        ).then((value) => {
                            draw_timeline();
                            $('#modal_add_event').modal('hide');

                        });
                    } else {
                        $('#submit_new_event').text('Save again');
                        swal("Oh no !", data.message, "error")
                    }
                },
                error: function (error) {
                    $('#submit_new_event').text('Save');
                    propagate_form_api_errors(error.responseJSON.data);
                }
            });
        
            return false;
        })

    });
   
    $('#modal_add_event').modal({ show: true });
}

function update_event(id) {
    window.location.hash = id;
    clear_api_error();
    var data_sent = $('#form_new_event').serializeObject();
    data_sent['event_date'] = $('#event_date').val();
    data_sent['event_time'] = $('#event_time').val();
    data_sent['event_in_summary'] = $('#event_in_summary').is(':checked');
    data_sent['event_in_graph'] = $('#event_in_graph').is(':checked');
    data_sent['event_tags'] = $('#event_tags').val();
    data_sent['event_assets'] = $('#event_assets').val();
    data_sent['event_tz'] = $('#event_tz').val();

    $.ajax({
        url: 'timeline/event/update/' + id + case_param(),
        type: "POST",
        data: JSON.stringify(data_sent),
        contentType: "application/json;charset=UTF-8",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                swal("Done !",
                "Updated successfully",
                    {
                        icon: "success",
                        timer: 400
                    }
                ).then((value) => {
                    draw_timeline();
                    $('#modal_add_event').modal('hide');

                });
            } else {
                $('#submit_new_event').text('Save again');
                swal("Oh no !", data.message, "error");
            }
        },
        error: function (error) {
            $('#submit_new_event').text('Save');
            propagate_form_api_errors(error.responseJSON.data);
        }
    });
}


/* Delete an event from the timeline thank to its id */ 
function delete_event(id) {
    window.location.hash = id;
    $.ajax({
        url: "timeline/event/delete/" + id + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                swal("Done !",
                     data.message,
                    {
                        icon: "success",
                        timer: 500
                    }
                );
                $('#modal_add_event').modal('hide');
                draw_timeline()
            } else {
                swal("Oh no !", data.message, "error")
            }
        },
        error: function (error) {
            notify_error(error.statusText);
        }
    });
}

/* Edit and event from the timeline thanks to its ID */
function edit_event(id) {
  url = '/case/timeline/event/' + id + '/modal' + case_param();
  window.location.hash = id;
  $('#modal_add_event_content').load(url, function(){
        $('#modal_add_event').modal({show:true});
  });
}

/* Fetch and draw the timeline */
function draw_timeline() {
    $('#timeline_list').empty();
    show_loader();
    rid = $('#assets_timeline_select').val();
    if (rid == null) { rid = 0; }

    $.ajax({
        url: "timeline/get/" + rid + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                var is_i = false;
                tmb = [];
                reid = $('#assets_timeline_select').val();
                if (reid == null) { reid = 0; }

                $('#assets_timeline_select').empty();
                $('#time_timeline_select').empty();


                /* Build the filter list */
                $('#assets_timeline_select').append('<option value="0">All assets</options>');
                for (rid in data.data.assets) {
                    $('#assets_timeline_select').append('<option value="'+sanitizeHTML(rid)+'">' + sanitizeHTML(data.data.assets[rid]) + '</options>');
                }
                $('#assets_timeline_select').selectpicker('val', reid);

                $('#assets_timeline_select').selectpicker("refresh");
                var tesk = false;
                // Prepare replacement mod
                var reap = [];
                ioc_list = data.data.iocs;
                for (ioc in ioc_list) {
                    // When an IOC contains another IOC in its description, we want to avoid to replace that particular pattern
                    var avoid_inception_start = "(?!<span[^>]*?>)("
                    var avoid_inception_end = ")(?![^<]*?</span>)"
                    var re = new RegExp(avoid_inception_start
                           + " " + escapeRegExp(ioc_list[ioc][1]) + " "
                           + avoid_inception_end
                           ,"g");
                    replacement = ' <span class="text-warning-high ml-1 link_asset" data-toggle="popover" style="cursor: pointer;" data-content="'+ sanitizeHTML(ioc_list[ioc][2]) + '" title="IOC">'+ sanitizeHTML(ioc_list[ioc][1]) + '</span> ';
                    reap.push([re, replacement]);
                }
                idx = 0;
                for (index in data.data.tim) {
                    evt = data.data.tim[index];
                    dta =  evt.event_date.split('T');
                    tags = '';
                    tmb_d = '';
                    style = '';
                    asset = '';

                    /* If IOC then build a tag */
                    if(evt.category_name && evt.category_name != 'Unspecified') {
                        tags += '<span class="badge badge-light ml-2 mb-1">' + sanitizeHTML(evt.category_name) +'</span>';
                    }

                    /* Do we have a border color to set ? */
                    style = " style='";
                    if (tesk) {
                        style += "background-color: #f0f0f0;";
                        tesk = false;
                    } else {
                        tesk = true;
                    }


                    if (evt.event_color != null) {
                            style += "border-left: 2px groove " + sanitizeHTML(evt.event_color);
                    }

                    style += ";'";

                    /* For every assets linked to the event, build a link tag */
                    if (evt.assets != null) {
                        for (ide in evt.assets) {
                            cpn =  evt.assets[ide]["ip"] + ' - ' + evt.assets[ide]["description"]
                            cpn = sanitizeHTML(cpn)
                            if (evt.assets[ide]["compromised"]) {
                                asset += '<span class="text-warning-high mr-2 link_asset" data-toggle="popover" style="cursor: pointer;" data-content="'+ cpn + '" title="' + sanitizeHTML(evt.assets[ide]["name"]) + '"><i class="fas fa-crosshdairs mr-1 ml-2 text-danger"></i>'+ sanitizeHTML(evt.assets[ide]["name"]) + '</span>|';
                            } else {
                                asset += '<span class="text-primary mr-2 ml-2 link_asset" data-toggle="popover" style="cursor: pointer;" data-content="'+ cpn + '" title="' + sanitizeHTML(evt.assets[ide]["name"]) + '">'+ sanitizeHTML(evt.assets[ide]["name"]) + '</span>|';
                            }
                        }
                    }

                    ori_date = '<span class="ml-3"></span>';
                    if (evt.event_date_wtz != evt.event_date) {
                        ori_date += `<i class="fas fa-info-circle mr-1" title="Locale date time ` + evt.event_date_wtz + evt.event_tz + `"></i>`
                    }

                    if(evt.event_in_summary) {
                        ori_date += `<i class="fas fa-newspaper mr-1" title="Showed in summary"></i>`
                    }

                    if(evt.event_in_graph) {
                        ori_date += `<i class="fas fa-share-alt mr-1" title="Showed in graph"></i>`
                    }

                    if (evt.event_tags != null) {
                    sp_tag = evt.event_tags.split(',');
                    for (tag_i in sp_tag) {
                            tags += '<span class="badge badge-light ml-2 mb-1">' + sanitizeHTML(sp_tag[tag_i]) + '</span>';
                        }
                    }

                    day = dta[0];
                    if (!tmb.includes(day)) {
                        tmb.push(day);
                        tmb_d = '<div class="time-badge" id="time_'+ idx +'"><small class="text-muted">'+ day + '</small><br/></div>';
                        idx += 1;
                    }

                    title_parsed = match_replace_ioc(sanitizeHTML(evt.event_title), reap);
                    content_parsed = sanitizeHTML(evt.event_content).replace(/&#13;&#10;/g, '<br/>');

                    if (content_parsed.length > 150) {
                        short_content = match_replace_ioc(content_parsed.slice(0, 150), reap);
                        formatted_content = short_content + `<div class="collapse" id="collapseContent">
                            `+ match_replace_ioc(content_parsed.slice(150), reap) +`
                        </div>
                        <a class="btn btn-link btn-sm" data-toggle="collapse" href="#collapseContent" role="button" aria-expanded="false" aria-controls="collapseContent">&gt; See more</a>`;
                    } else {
                        formatted_content = match_replace_ioc(content_parsed, reap);
                    }

                    entry = `<li class="timeline-inverted" title="Event ID #`+ evt.event_id + `">
                        ` + tmb_d + `
                            <div class="timeline-panel" `+ style +` id="event_`+ evt.event_id + `" >
                                <div class="timeline-heading">
                                    <div class="btn-group dropdown float-right">
                                        <button type="button" class="btn btn-xs" onclick="edit_event(`+ evt.event_id +`)">
                                            <span class="btn-label">
                                                <i class="fa fa-pen"></i>
                                            </span>
                                        </button>
                                        <button type="button" class="btn btn-xs dropdown-toggle" data-toggle="dropdown" aria-expanded="false">
                                            <span class="btn-label">
                                                <i class="fa fa-cog"></i>
                                            </span>
                                        </button>
                                        <ul class="dropdown-menu" role="menu" x-placement="bottom-start" style="position: absolute; transform: translate3d(0px, 32px, 0px); top: 0px; left: 0px; will-change: transform;">
                                            <li>
                                                <a class="dropdown-item" onclick="delete_event(`+ evt.event_id +`);">Delete</a>
                                            </li>
                                        </ul>
                                    </div>
                                    <div class="row mb-2">
                                        <a class="timeline-title" style="color: rgb(75, 79, 87);">` + title_parsed + `</a>
                                    </div>
                                </div>
                                <div class="timeline-body text-faded" style="color: rgb(130, 130, 130);">
                                    <span>` + formatted_content + `</span>
                                </div>
                                <div class="bottom-hour mt-2">
                                    <span class="float-right">`+ asset + tags +`</span>
                                    <span class="text-muted text-sm float-left mb--2"><small><i class="flaticon-stopwatch mr-2"></i>`+ evt.event_date + ori_date + `</small></span>
                                <div>
                            </div>
                        </li>`
                    is_i = false;

                    //entry = match_replace_ioc(entry, reap);
                    $('#timeline_list').append(entry);

                }

                //match_replace_ioc(data.data.iocs, "timeline_list");
                $('[data-toggle="popover"]').popover();

                if (location.href.indexOf("#") != -1) {
                    var current_url = window.location.href;
                    // Capture the string after #

                    var id = current_url.substr(current_url.indexOf("#") + 1);
                    if ($('#event_'+id).offset() != undefined) {
                        $('html, body').animate({ scrollTop: $('#event_'+id).offset().top - 180 });
                    }
                }

                for (tm in tmb) {
                    $('#time_timeline_select').append('<option value="'+ tm +'">' +tmb[tm] + '</options>');
                }

                $('#time_timeline_select').selectpicker("refresh");
                last_state = data.data.state.object_state;
                hide_loader();

            } else {
                swal.close();
                $('#submit_new_event').text('Save again');
                swal("Oh no !", data.message, "error")
            }
        },
        error: function (error) {
            swal.close();
            $('#submit_new_event').text('Save');
            swal("Oh no !", error.statusText, "error")
        }
    }).done(function() {goToSharedLink()});
}

function escapeRegExp(text) {
    return text.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&');
}

function match_replace_ioc(entry, reap) {
    for (rak in reap) {
        entry = entry.replace(reap[rak][0], reap[rak][1]);
    }
    return entry;
}

function to_page_up() {
  document.body.scrollTop = 0; // For Safari
  document.documentElement.scrollTop = 0; // For Chrome, Firefox, IE and Opera
}

function to_page_down() {
    window.scrollTo(0,document.body.scrollHeight);
  }

$('#time_timeline_select').on('change', function(e){ 
    id = $('#time_timeline_select').val();
    $('html, body').animate({ scrollTop: $('#time_'+id).offset().top - 180 });
});


function goToSharedLink(){
   shared_id = getSharedLink();
   console.log('161');
   if (shared_id) {
        $('html, body').animate({ scrollTop: $('#event_'+shared_id).offset().top - 80 });
        console.log('161');
        $('#event_'+shared_id).addClass('fade-it');
    }
}


/* Page is ready, fetch the assets of the case */
$(document).ready(function(){

    draw_timeline();

    setInterval(function() { check_update('timeline/state'); }, 3000);

    if (location.href.indexOf("#") != -1) {
        var current_url = window.location.href;
        // Capture the string after #
        var id = current_url.substr(current_url.indexOf("#") + 1);
        if ($('#event_'+id).offset() != undefined) {
            $('html, body').animate({ scrollTop: $('#event_'+id).offset().top - 180 });
        }
    }
});