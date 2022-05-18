var tm_filter = ace.edit("timeline_filtering",
{
    autoScrollEditorIntoView: true,
    minLines: 1,
    maxLines: 5
});
tm_filter.setTheme("ace/theme/tomorrow");
tm_filter.session.setMode("ace/mode/json");
tm_filter.renderer.setShowGutter(false);
tm_filter.setShowPrintMargin(false);
tm_filter.renderer.setScrollMargin(10, 10);
tm_filter.setOption("displayIndentGuides", true);
tm_filter.setOption("indentedSoftWrap", true);
tm_filter.setOption("showLineNumbers", false);
tm_filter.setOption("placeholder", "Filter timeline");
tm_filter.setOption("highlightActiveLine", false);
tm_filter.commands.addCommand({
                    name: "Do filter",
                    bindKey: { win: "Enter", mac: "Enter" },
                    exec: function (editor) {
                              filter_timeline();
                    }
});
var selector_active;
var current_timeline;

/* Fetch a modal that allows to add an event */
function add_event() {
    url = 'timeline/events/add/modal' + case_param();
    $('#modal_add_event_content').load(url, function (response, status, xhr) {
        hide_minimized_modal_box();
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        $('#submit_new_event').on("click", function () {
            clear_api_error();
            var data_sent = $('#form_new_event').serializeObject();
            data_sent['event_date'] = `${$('#event_date').val()}T${$('#event_time').val()}`;
            data_sent['event_in_summary'] = $('#event_in_summary').is(':checked');
            data_sent['event_in_graph'] = $('#event_in_graph').is(':checked');
            data_sent['event_tags'] = $('#event_tags').val();
            data_sent['event_assets'] = $('#event_assets').val();
            data_sent['event_iocs'] = $('#event_iocs').val();
            data_sent['event_tz'] = $('#event_tz').val();
            ret = get_custom_attributes_fields();
            has_error = ret[0].length > 0;
            attributes = ret[1];

            if (has_error){return false;}

            data_sent['custom_attributes'] = attributes;

            post_request_api('timeline/events/add', JSON.stringify(data_sent), true)
            .done((data) => {
                if(notify_auto_api(data)) {
                    window.location.hash = data.data.event_id;
                    apply_filtering();
                    $('#modal_add_event').modal('hide');
                }
            });

            return false;
        })
    });
   
    $('#modal_add_event').modal({ show: true });
}


function duplicate_event(id) {
    window.location.hash = id;
    clear_api_error();

    get_request_api("timeline/events/duplicate/" + id)
    .done((data) => {
        if(notify_auto_api(data)) {
            apply_filtering();
        }
    });

}

function update_event(id) {
    window.location.hash = id;
    clear_api_error();
    var data_sent = $('#form_new_event').serializeObject();
    data_sent['event_date'] = `${$('#event_date').val()}T${$('#event_time').val()}`;
    data_sent['event_in_summary'] = $('#event_in_summary').is(':checked');
    data_sent['event_in_graph'] = $('#event_in_graph').is(':checked');
    data_sent['event_tags'] = $('#event_tags').val();
    data_sent['event_assets'] = $('#event_assets').val();
    data_sent['event_iocs'] = $('#event_iocs').val();
    data_sent['event_tz'] = $('#event_tz').val();
    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;

    post_request_api('timeline/events/update/' + id, JSON.stringify(data_sent), true)
    .done(function(data) {
        if(notify_auto_api(data)) {
            apply_filtering();
            $('#modal_add_event').modal('hide');
        }
    });

}


/* Delete an event from the timeline thank to its id */ 
function delete_event(id) {
    window.location.hash = id;

    get_request_api("timeline/events/delete/" + id)
    .done(function(data) {
        if(notify_auto_api(data)) {
            apply_filtering();
            $('#modal_add_event').modal('hide');
        }
    });

}

/* Edit an event from the timeline thanks to its ID */
function edit_event(id) {
  url = '/case/timeline/events/' + id + '/modal' + case_param();
  window.location.hash = id;
  $('#modal_add_event_content').load(url, function (response, status, xhr) {
        hide_minimized_modal_box();
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }
        load_menu_mod_options_modal(id, 'event', $("#event_modal_quick_actions"));
        $('#modal_add_event').modal({show:true});
  });
}

function is_timeline_compact_view() {
    var x = getCookie('iris_tm_compact');
    if (typeof x !== 'undefined') {
        if (x === 'true') {
            return true;
        }
    }
    return false;
}

function toggle_compact_view() {
    var x = getCookie('iris_tm_compact');
    if (typeof x === 'undefined') {
        setCookie('iris_tm_compact', 'true', 365);
        location.reload();
    } else {
        if (x === 'true') {
            setCookie('iris_tm_compact', 'false', 365);
            location.reload();
        } else {
            setCookie('iris_tm_compact', 'true', 365);
            location.reload();
        }
    }
}

function toggle_selector() {
    //activating selector toggle
    if(selector_active == false) {
        selector_active = true;

        //blend in conditional buttons to perform actions on selected rows - e.g. select graph, summary, color
        $(".btn-conditional").show(250);
        //highligh the selection button
        $("#selector-btn").addClass("btn-active");
        //$("#selector-btn").load();
        //remove data toggle attribute to disable expand feature
        $("[id^=dropa_]").removeAttr('data-toggle');

        //create click handler for timeline events
        $(".timeline li .timeline-panel").on('click', function(){
            if($(this).hasClass("timeline-selected")) {
                $(this).removeClass("timeline-selected");
            } else {
                $(this).addClass("timeline-selected");
            }
        });
    

    }

    //deactivating selector toggle
    else if(selector_active == true) {
        selector_active = false;
        $(".btn-conditional").hide(250);
        $(".btn-conditional-2").hide(250);
        $("#selector-btn").removeClass("btn-active");
        //restore the collapse feature
        $("[id^=dropa_]").attr('data-toggle','collapse');
        $(".timeline-selected").removeClass("timeline-selected");

        $(".timeline li .timeline-panel").off('click');
        apply_filtering();
    }
}

function toggle_colors() { 
    // console.log("toggling colors");
    var color_buttons = $(".btn-conditional-2");
    color_buttons.slideToggle(250);
    // console.log(color_buttons);
}

function events_set_attribute(attribute, color) {

    var attribute_value;

    var selected_rows = $(".timeline-selected");

    if(selected_rows.length <= 0) {
        console.log("no rows selected, returning");
        return true;
    }

    switch(attribute) {
        case "event_in_graph":
            break;
        case "event_in_summary":
            break;
        case "event_color":
            attribute_value = color;
            var color_buttons = $(".btn-conditional-2");
            color_buttons.slideToggle(250);
            break;
        default:
            console.log("invalid argument given");
            return false;
    }

    //loop through events and toggle/set selected attribute
    selected_rows.each(function(index) {
        var object = selected_rows[index];
        var event_id = object.getAttribute('id').replace("event_",""); 

        var original_event;

        //get event data
        get_request_api("timeline/events/" + event_id)
        .done((data) => {
            original_event = data.data;
            if(notify_auto_api(data, true)) {
                //change attribute to selected value
                if(attribute == 'event_in_graph' || attribute == 'event_in_summary'){
                    attribute_value = original_event[attribute];
                    original_event[attribute] = !attribute_value;
                } else if(attribute == 'event_color') {
                    // attribute value already set to color L240
                    original_event[attribute] = attribute_value;
                }

                //get csrf token
                var csrf_token = $("#csrf_token").val();

                //add csrf token to request
                original_event['csrf_token'] = csrf_token;

                //send updated event to API
                post_request_api('timeline/events/update/' + event_id, JSON.stringify(original_event), true)
                .done(function(data) {
                    notify_auto_api(data);
                    if (index === selected_rows.length - 1) {
                        get_or_filter_tm(function() {
                            selected_rows.each(function() {
                                var event_id = this.getAttribute('id')
                                $('#' + event_id).addClass("timeline-selected");
                            });
                        });
                    }
                });
            }
        });
    });
}

function events_bulk_delete() {
    var selected_rows = $(".timeline-selected");
    if(selected_rows.length <= 0) {
        console.log("no rows selected, returning");
        return true;
    }

    swal({
        title: "Are you sure?",
        text: "You are about to delete " + selected_rows.length + " events.\nThere is no coming back.",
        icon: "warning",
        buttons: true,
        dangerMode: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, delete them'
    })
    .then((willDelete) => {
        if (willDelete) {
            selected_rows.each(function(index) {
                var object = selected_rows[index];
                var event_id = object.getAttribute('id').replace("event_","");
                get_request_api("timeline/events/delete/" + event_id)
                .done(function(data) {
                    notify_auto_api(data);
                    if (index === selected_rows.length - 1) {
                        get_or_filter_tm();
                    }
                });
            });
        } else {
            swal("Pfew, that was close");
        }
    });
}


function build_timeline(data) {
    var compact = is_timeline_compact_view();
    var is_i = false;
    current_timeline = data.data.tim;
    tmb = [];

    reid = 0;

    $('#time_timeline_select').empty();

    var standard_filters = [
                {value: 'asset:', score: 10, meta: 'Match assets of events'},
                {value: 'startDate:', score: 10, meta: 'Match end date of events'},
                {value: 'endDate:', score: 10, meta: 'Match end date of events'},
                {value: 'tag:', score: 10, meta: 'Match tag of events'},
                {value: 'description:', score: 10, meta: 'Match description of events'},
                {value: 'category:', score: 10, meta: 'Match category of events'},
                {value: 'title:', score: 10, meta: 'Match title of events'},
                {value: 'source:', score: 10, meta: 'Match source of events'},
                {value: 'raw:', score: 10, meta: 'Match raw data of events'},
                {value: 'ioc', score: 10, meta: "Match ioc in events"},
                {value: 'AND ', score: 10, meta: 'AND operator'}
              ]

    for (rid in data.data.assets) {
        standard_filters.push(
             {value: data.data.assets[rid][0], score: 1, meta: data.data.assets[rid][1]}
        );
    }

    for (rid in data.data.categories) {
        standard_filters.push(
             {value: data.data.categories[rid], score: 1, meta: "Event category"}
        );
    }

    tm_filter.setOptions({
          enableBasicAutocompletion: [{
            getCompletions: (editor, session, pos, prefix, callback) => {
              callback(null, standard_filters);
            },
          }],
          enableLiveAutocompletion: true,
    });

    var tesk = false;
    // Prepare replacement mod
    var reap = [];
    ioc_list = data.data.iocs;
    for (ioc in ioc_list) {

        var capture_start = "(^|" + sanitizeHTML(";") + "|" + sanitizeHTML(":") + "|" + sanitizeHTML("|")
            + "|" + sanitizeHTML(">") + "|" + sanitizeHTML("<") + "|" + sanitizeHTML("[") + "|"
            + sanitizeHTML("]") + "|" + sanitizeHTML("(") + "|" + sanitizeHTML(")") + "| |\>)(";
        var capture_end = ")(" + sanitizeHTML(";") + "|" + sanitizeHTML(":") + "|" + sanitizeHTML("|")
            + "|" + sanitizeHTML(">") + "|" + sanitizeHTML("<") + "|" + sanitizeHTML("[") + "|"
            + sanitizeHTML("]") + "|" + sanitizeHTML("(") + "|" + sanitizeHTML(")") + "| |>|$|<br/>)";
        // When an IOC contains another IOC in its description, we want to avoid to replace that particular pattern
        var avoid_inception_start = "(?!<span[^>]*?>)" + capture_start;
        var avoid_inception_end = "(?![^<]*?<\/span>)" + capture_end;
        var re = new RegExp(avoid_inception_start
               + escapeRegExp(sanitizeHTML(ioc_list[ioc]['ioc_value']))
               + avoid_inception_end
               ,"g");
        replacement = `$1<span class="text-warning-high ml-1 link_asset" data-toggle="popover" style="cursor: pointer;" data-trigger="hover" data-content="${sanitizeHTML(ioc_list[ioc]['ioc_description'])}" title="IOC">${sanitizeHTML(ioc_list[ioc]['ioc_value'])}</span> $3`;
        reap.push([re, replacement]);
    }
    idx = 0;

    for (index in data.data.tim) {
        evt = data.data.tim[index];
        dta =  evt.event_date.split('T');
        tags = '';
        cats = '';
        tmb_d = '';
        style = '';
        asset = '';
        

        if(evt.category_name && evt.category_name != 'Unspecified') {
            tags += `<span class="badge badge-light float-right mr-2 mb-1">${sanitizeHTML(evt.category_name)}</span>`;
            if (evt.category_name != 'Unspecified') {
                cats += `<span class="badge badge-light float-right mr-2 mb-1">${sanitizeHTML(evt.category_name)}</span>`;
            }
        }
        
        if (evt.iocs != null && evt.iocs.length > 0) {
            for (ioc in evt.iocs) {
                tags += `<span class="badge badge-warning-event float-right mr-2 mb-1" data-toggle="popover" data-trigger="hover" style="cursor: pointer;" data-content="IOC - ${sanitizeHTML(evt.iocs[ioc].description)}"><i class="fa-solid fa-virus-covid"></i> ${sanitizeHTML(evt.iocs[ioc].name)}</span>`;
            }
        }

        if (evt.event_tags != null && evt.event_tags.length > 0) {
            sp_tag = evt.event_tags.split(',');
            for (tag_i in sp_tag) {
                    tags += `<span class="badge badge-light float-right mr-2 mb-1">${sanitizeHTML(sp_tag[tag_i])}</span>`;
                }
        }

        /* Do we have a border color to set ? */
        style = "";
        if (tesk) {
            style += "timeline-odd";
            tesk = false;
        } else {
            style += "timeline-even";
            tesk = true;
        }

        style_s = "style='";
        if (evt.event_color != null) {
                style_s += "border-left: 2px groove " + sanitizeHTML(evt.event_color);
        }

        style_s += ";'";

        /* For every assets linked to the event, build a link tag */
        if (evt.assets != null) {
            for (ide in evt.assets) {
                cpn =  evt.assets[ide]["ip"] + ' - ' + evt.assets[ide]["description"]
                cpn = sanitizeHTML(cpn)
                if (evt.assets[ide]["compromised"]) {
                    asset += `<span class="badge badge-warning-event mr-2 float-right link_asset mb-1" data-toggle="popover" data-trigger="hover" style="cursor: pointer;" data-content="${cpn}" title="${sanitizeHTML(evt.assets[ide]["name"])}">${sanitizeHTML(evt.assets[ide]["name"])}</span>`;
                } else {
                    asset += `<span class="badge badge-light mr-2 float-right link_asset mb-1" data-toggle="popover" data-trigger="hover" style="cursor: pointer;" data-content="${cpn}" title="${sanitizeHTML(evt.assets[ide]["name"])}">${sanitizeHTML(evt.assets[ide]["name"])}</span>`;
                }
            }
        }

        ori_date = '<span class="ml-3"></span>';
        if (evt.event_date_wtz != evt.event_date) {
            ori_date += `<i class="fas fa-info-circle mr-1" title="Locale date time ${evt.event_date_wtz}${evt.event_tz}"></i>`
        }

        if(evt.event_in_summary) {
            ori_date += `<i class="fas fa-newspaper mr-1" title="Showed in summary"></i>`
        }

        if(evt.event_in_graph) {
            ori_date += `<i class="fas fa-share-alt mr-1" title="Showed in graph"></i>`
        }
        

        day = dta[0];
        mtop_day = '';
        if (!tmb.includes(day)) {
            tmb.push(day);
            if (!compact) {
                tmb_d = `<div class="time-badge" id="time_${idx}"><small class="text-muted">${day}</small><br/></div>`;
            } else {
                tmb_d = `<div class="time-badge-compact" id="time_${idx}"><small class="text-muted">${day}</small><br/></div>`;
            }
            idx += 1;
            mtop_day = 'mt-4';
        }

        title_parsed = match_replace_ioc(sanitizeHTML(evt.event_title), reap);
        content_parsed = sanitizeHTML(evt.event_content).replace(/&#13;&#10;/g, '<br/>');

        if (!compact) {
            content_split = content_parsed.split('<br/>');
            lines = content_split.length;
            if (content_parsed.length > 150 || lines > 2) {
                if (lines > 2) {
                    short_content = match_replace_ioc(content_split.slice(0,2).join('<br/>'), reap);
                    long_content = match_replace_ioc(content_split.slice(2).join('<br/>'), reap);
                } else {
                    offset = content_parsed.slice(150).indexOf(' ');
                    short_content = match_replace_ioc(content_parsed.slice(0, 150 + offset), reap);
                    long_content = match_replace_ioc(content_parsed.slice(150 + offset), reap);
                }
                formatted_content = short_content + `<div class="collapse" id="collapseContent-${evt.event_id}">
                ${long_content}
                </div>
                <a class="btn btn-link btn-sm" data-toggle="collapse" href="#collapseContent-${evt.event_id}" role="button" aria-expanded="false" aria-controls="collapseContent">&gt; See more</a>`;
            } else {
                formatted_content = match_replace_ioc(content_parsed, reap);
            }
        }

        shared_link = buildShareLink(evt.event_id);

        if (compact) {
            entry = `<li class="timeline-inverted ${mtop_day}" title="Event ID #${evt.event_id}">
                ${tmb_d}
                    <div class="timeline-panel ${style}" ${style_s} id="event_${evt.event_id}" >
                        <div class="timeline-heading">
                            <div class="btn-group dropdown float-right">
                                ${cats}
                                <button type="button" class="btn btn-light btn-xs" onclick="edit_event(${evt.event_id})" title="Edit">
                                    <span class="btn-label">
                                        <i class="fa fa-pen"></i>
                                    </span>
                                </button>
                                <button type="button" class="btn btn-light btn-xs dropdown-toggle" data-toggle="dropdown" aria-expanded="false">
                                    <span class="btn-label">
                                        <i class="fa fa-cog"></i>
                                    </span>
                                </button>
                                <div class="dropdown-menu" role="menu" x-placement="bottom-start" style="position: absolute; transform: translate3d(0px, 32px, 0px); top: 0px; left: 0px; will-change: transform;">
                                        <a href= "#" class="dropdown-item" onclick="copy_object_link(${evt.event_id});return false;"><small class="fa fa-share mr-2"></small>Share</a>
                                        <a href= "#" class="dropdown-item" onclick="duplicate_event(${evt.event_id});return false;"><small class="fa fa-clone mr-2"></small>Duplicate</a>
                                        <div class="dropdown-divider"></div>
                                        <a href= "#" class="dropdown-item text-danger" onclick="delete_event(${evt.event_id});"><small class="fa fa-trash mr-2"></small>Delete</a>
                                </div>
                            </div>
                            <div class="collapsed" id="dropa_${evt.event_id}" data-toggle="collapse" data-target="#drop_${evt.event_id}" aria-expanded="false" aria-controls="drop_${evt.event_id}" role="button" style="cursor: pointer;">
                                <span class="text-muted text-sm float-left mb--2"><small>${evt.event_date}</small></span>
                                <a class="text-dark text-sm ml-3" href="${shared_link}" onclick="edit_event(${evt.event_id});return false;">${title_parsed}</a>
                            </div>
                        </div>
                        <div class="timeline-body text-faded" >
                            <div id="drop_${evt.event_id}" class="collapse" aria-labelledby="dropa_${evt.event_id}" style="">
                                <div class="card-body">
                                ${content_parsed}
                                </div>
                                <div class="bottom-hour mt-2">
                                    <span class="float-right">${tags}${asset} </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </li>`
        } else {
            entry = `<li class="timeline-inverted" title="Event ID #${evt.event_id}">
                    ${tmb_d}
                    <div class="timeline-panel ${style}" ${style_s} id="event_${evt.event_id}" >
                        <div class="timeline-heading">
                            <div class="btn-group dropdown float-right">

                                <button type="button" class="btn btn-light btn-xs" onclick="edit_event(${evt.event_id})" title="Edit">
                                    <span class="btn-label">
                                        <i class="fa fa-pen"></i>
                                    </span>
                                </button>
                                <button type="button" class="btn btn-light btn-xs dropdown-toggle" data-toggle="dropdown" aria-expanded="false">
                                    <span class="btn-label">
                                        <i class="fa fa-cog"></i>
                                    </span>
                                </button>
                                <div class="dropdown-menu" role="menu" x-placement="bottom-start" style="position: absolute; transform: translate3d(0px, 32px, 0px); top: 0px; left: 0px; will-change: transform;">
                                        <a href= "#" class="dropdown-item" onclick="copy_object_link(${evt.event_id});return false;"><small class="fa fa-share mr-2"></small>Share</a>
                                        <a href= "#" class="dropdown-item" onclick="duplicate_event(${evt.event_id});return false;"><small class="fa fa-clone mr-2"></small>Duplicate</a>
                                        <div class="dropdown-divider"></div>
                                        <a href= "#" class="dropdown-item text-danger" onclick="delete_event(${evt.event_id});"><small class="fa fa-trash mr-2"></small>Delete</a>
                                </div>
                            </div>
                            <div class="row mb-2">
                                <a class="timeline-title" href="${shared_link}" onclick="edit_event(${evt.event_id});return false;">${title_parsed}</a>
                            </div>
                        </div>
                        <div class="timeline-body text-faded" >
                            <span>${formatted_content}</span>
                        </div>
                        <div class="bottom-hour mt-2">
                            <div class="row">
                                <div class="col-4 d-flex">
                                    <span class="text-muted text-sm align-self-end float-left mb--2"><small><i class="flaticon-stopwatch mr-2"></i>${evt.event_date}${ori_date}</small></span>
                                </div>
                                <div class="col-8 ">
                                    <span class="float-right">${tags}${asset} </span>
                                </div>
                            </div>
                        <div>
                    </div>
                </li>`
        }
        is_i = false;

        //entry = match_replace_ioc(entry, reap);
        $('#timeline_list').append(entry);


    }
    //match_replace_ioc(data.data.iocs, "timeline_list");
    $('[data-toggle="popover"]').popover();

    if (data.data.tim.length === 0) {
       $('#timeline_list').append('<h3 class="ml-mr-auto text-center">No events in current view</h3>');
    }

    set_last_state(data.data.state);
    hide_loader();

    if (location.href.indexOf("#") != -1) {
        var current_url = window.location.href;
        var id = current_url.substr(current_url.indexOf("#") + 1);
        if ($('#event_'+id).offset() != undefined) {
            $('html, body').animate({ scrollTop: $('#event_'+id).offset().top - 180 });
            $('#event_'+id).addClass('fade-it');
        }
    }

    // re-enable onclick event on timeline if selector_active is true
    if(selector_active == true) {
        $(".timeline li .timeline-panel").on('click', function(){
            if($(this).hasClass("timeline-selected")) {
                $(this).removeClass("timeline-selected");
            } else {
                $(this).addClass("timeline-selected");
            }
        });
    }
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

function show_time_converter(){
    $('#event_date_convert').show();
    $('#event_date_convert_input').focus();
    $('#event_date_inputs').hide();
}

function hide_time_converter(){
    $('#event_date_convert').hide();
    $('#event_date_inputs').show();
    $('#event_date').focus();
}

function time_converter(){
    date_val = $('#event_date_convert_input').val();

    var data_sent = Object();
    data_sent['date_value'] = date_val;
    data_sent['csrf_token'] = $('#csrf_token').val();

    post_request_api('timeline/events/convert-date', JSON.stringify(data_sent))
    .done(function(data) {
        if(notify_auto_api(data)) {
            $('#event_date').val(data.data.date);
            $('#event_time').val(data.data.time);
            $('#event_tz').val(data.data.tz);
            hide_time_converter();
            $('#convert_bad_feedback').text('');
        }
    })
    .fail(function() {
        $('#convert_bad_feedback').text('Unable to find a matching pattern for the date');
    });
}


function goToSharedLink(){
    if (location.href.indexOf("#") != -1) {
        var current_url = window.location.href;
        var id = current_url.substr(current_url.indexOf("#") + 1);
        if ($('#event_'+id).offset() != undefined) {
            return;
        }
   }
   shared_id = getSharedLink();
   if (shared_id) {
        $('html, body').animate({ scrollTop: $('#event_'+shared_id).offset().top - 80 });
        $('#event_'+shared_id).addClass('fade-it');
    }
}

function timelineToCsv(){
    csv_data = "event_date(UTC),event_title,event_description,event_tz,event_date_wtz,event_category,event_tags,linked_assets,linked_iocs\n";
    for (index in current_timeline) {
        item = current_timeline[index];
        content = item.event_content.replace(/"/g, '\"');
        content_parsed = content.replace(/(\r?\n)+/g, ' - ');
        title = item.event_title.replace(/"/g, '\"');
        tags = item.event_tags.replace(/"/g, '\"');
        assets = "";
        for (k in item.assets) {
            asset = item.assets[k].name.replace(/"/g, '\"');
            assets += `${asset};`;
        }
        iocs = "";
        for (k in item.iocs) {
            ioc = item.iocs[k].name.replace(/"/g, '\"');
            iocs += `${ioc};`;
        }
        csv_data += `"${item.event_date}","${title}","${content_parsed}","${item.event_tz}","${item.event_date_wtz}","${item.category_name}","${tags}","${assets}","${iocs}"\n`;
    }
    download_file("iris_timeline.csv", "text/csv", csv_data);
}

function timelineToCsvWithUI(){
    csv_data = "event_date(UTC),event_title,event_description,event_tz,event_date_wtz,event_category,event_tags,linked_assets,linked_iocs,created_by,creation_date\n";
    for (index in current_timeline) {

        item = current_timeline[index];
        content = item.event_content.replace(/"/g, '\"');
        content_parsed = content.replace(/(\r?\n)+/g, ' - ');
        title = item.event_title.replace(/"/g, '\"');
        tags = item.event_tags.replace(/"/g, '\"');
        assets = "";
        for (k in item.assets) {
            asset = item.assets[k].name.replace(/"/g, '\"');
            assets += `${asset};`;
        }
        iocs = "";
        for (k in item.iocs) {
            ioc = item.iocs[k].name.replace(/"/g, '\"');
            iocs += `${ioc};`;
        }
        csv_data += `"${item.event_date}","${title}","${content_parsed}","${item.event_tz}","${item.event_date_wtz}","${item.category_name}","${tags}","${assets}","${iocs}","${item.user}","${item.event_added}"\n`;
    }
    download_file("iris_timeline.csv", "text/csv", csv_data);
}


function split_bool(split_str) {
    and_split = split_str.split(' AND ');

    if (and_split[0]) {
      return and_split[0];
    }

    or_split = split_str.split(' OR ');

    if (or_split[0]) {
      return or_split[0].trim();
    }

    return null;
}

var parsed_filter = {};
var keywords = ['asset', 'tag', 'title', 'description', 'ioc', 'raw', 'category', 'source', 'startDate', 'endDate'];


function parse_filter(str_filter, keywords) {
  for (var k = 0; k < keywords.length; k++) {
  	keyword = keywords[k];
    items = str_filter.split(keyword + ':');

    ita = items[1];

    if (ita === undefined) {
    	continue;
    }

    item = split_bool(ita);

    if (item != null) {
      if (!(keyword in parsed_filter)) {
        parsed_filter[keyword] = [];
      }
      if (!parsed_filter[keyword].includes(item)) {
        parsed_filter[keyword].push(item.trim());
        console.log('Got '+ item.trim() + ' as ' + keyword);
      }

      if (items[1] != undefined) {
        str_filter = str_filter.replace(keyword + ':' + item, '');
        if (parse_filter(str_filter, keywords)) {
        	keywords.shift();
        }
      }
    }
  }
  return true;
}

function filter_timeline() {
    current_path = location.protocol + '//' + location.host + location.pathname;
    new_path = current_path + case_param() + '&filter=' + encodeURIComponent(tm_filter.getValue());
    window.location = new_path;
}

function reset_filters() {
    current_path = location.protocol + '//' + location.host + location.pathname;
    new_path = current_path + case_param();
    window.location = new_path;
}


function apply_filtering(post_req_fn) {
    keywords = ['asset', 'tag', 'title', 'description', 'ioc', 'category', 'source',  'raw', 'startDate', 'endDate'];
    parsed_filter = {};
    parse_filter(tm_filter.getValue(), keywords);
    filter_query = encodeURIComponent(JSON.stringify(parsed_filter));

    $('#timeline_list').empty();
    show_loader();
    get_request_data_api("/case/timeline/advanced-filter",{ 'q': filter_query })
    .done((data) => {
        if(notify_auto_api(data, true)) {
            build_timeline(data);
            if(post_req_fn !== undefined) {
                post_req_fn();
            }
        }
        goToSharedLink();
    });
}

function getFilterFromLink(){
    queryString = window.location.search;
    urlParams = new URLSearchParams(queryString);

    if (urlParams.get('filter') !== undefined) {
        return urlParams.get('filter')
    }
    return null;
}

function get_or_filter_tm(post_req_fn) {
    filter = getFilterFromLink();
    if (filter) {
        tm_filter.setValue(filter);
        apply_filtering(post_req_fn);
    } else {
        apply_filtering(post_req_fn);
    }
}


/* Page is ready, fetch the assets of the case */
$(document).ready(function(){

    selector_active = false;

    get_or_filter_tm();

    setInterval(function() { check_update('timeline/state'); }, 3000);

});

