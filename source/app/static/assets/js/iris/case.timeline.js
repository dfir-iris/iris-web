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


/* Fetch a modal that allows to add an event */
function add_event() {
    url = 'timeline/events/add/modal' + case_param();
    $('#modal_add_event_content').load(url, function () {   
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

            $.ajax({
                url: 'timeline/events/add' + case_param(),
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
                            window.location.hash = data.data.event_id;
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


function duplicate_event(id) {
    window.location.hash = id;
    clear_api_error();
    $.ajax({
        url: "timeline/events/duplicate/" + id + case_param(),
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

    $.ajax({
        url: 'timeline/events/update/' + id + case_param(),
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
        url: "timeline/events/delete/" + id + case_param(),
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

/* Edit an event from the timeline thanks to its ID */
function edit_event(id) {
  url = '/case/timeline/events/' + id + '/modal' + case_param();
  window.location.hash = id;
  $('#modal_add_event_content').load(url, function(){
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



var current_timeline;

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
        replacement = `$1<span class="text-warning-high ml-1 link_asset" data-toggle="popover" style="cursor: pointer;" data-content="${sanitizeHTML(ioc_list[ioc]['ioc_description'])}" title="IOC">${sanitizeHTML(ioc_list[ioc]['ioc_value'])}</span> $3`;
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

        /* If IOC then build a tag */
        if(evt.category_name && evt.category_name != 'Unspecified') {
            tags += `<span class="badge badge-light ml-2 mb-1">${sanitizeHTML(evt.category_name)}</span>`;
            if (evt.category_name != 'Unspecified') {
                cats += `<span class="badge badge-light mr-2 mb-1">${sanitizeHTML(evt.category_name)}</span>`;
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
                    asset += `<span class="text-warning-high mr-2 link_asset" data-toggle="popover" data-trigger="hover" style="cursor: pointer;" data-content="${cpn}" title="${sanitizeHTML(evt.assets[ide]["name"])}"><i class="fas fa-crosshdairs mr-1 ml-2 text-danger"></i>${sanitizeHTML(evt.assets[ide]["name"])}</span>|`;
                } else {
                    asset += `<span class="text-primary mr-2 ml-2 link_asset" data-toggle="popover" data-trigger="hover" style="cursor: pointer;" data-content="${cpn}" title="${sanitizeHTML(evt.assets[ide]["name"])}">${sanitizeHTML(evt.assets[ide]["name"])}</span>|`;
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

        if (evt.event_tags != null) {
        sp_tag = evt.event_tags.split(',');
        for (tag_i in sp_tag) {
                tags += `<span class="badge badge-light ml-2 mb-1">${sanitizeHTML(sp_tag[tag_i])}</span>`;
            }
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
            entry = `<li class="timeline-inverted ${mtop_day} " title="Event ID #${evt.event_id}">
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
                                    <span class="float-right">${asset}${tags}</span>
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
                            <span class="float-right">${asset}${tags}</span>
                            <span class="text-muted text-sm float-left mb--2"><small><i class="flaticon-stopwatch mr-2"></i>${evt.event_date}${ori_date}</small></span>
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

    last_state = data.data.state.object_state;
    hide_loader();

    if (location.href.indexOf("#") != -1) {
        var current_url = window.location.href;
        var id = current_url.substr(current_url.indexOf("#") + 1);
        if ($('#event_'+id).offset() != undefined) {
            $('html, body').animate({ scrollTop: $('#event_'+id).offset().top - 180 });
            $('#event_'+id).addClass('fade-it');
        }
    }
}

/* Fetch and draw the timeline */
function draw_timeline() {
    $('#timeline_list').empty();
    show_loader();
    rid = $('#assets_timeline_select').val();
    if (rid == null) { rid = 0; }

    $.ajax({
        url: "timeline/filter/" + rid + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                build_timeline(data);
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


    $.ajax({
        url: 'timeline/events/convert-date' + case_param(),
        type: "POST",
        data: JSON.stringify(data_sent),
        contentType: "application/json;charset=UTF-8",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                $('#event_date').val(data.data.date);
                $('#event_time').val(data.data.time);
                $('#event_tz').val(data.data.tz);
                hide_time_converter();
                $('#convert_bad_feedback').text('');
            }
        },
        error: function (error) {
            $('#convert_bad_feedback').text('Unable to find a matching pattern for the date');
        }
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
    csv_data = "event_date(UTC),event_title,event_description,event_tz,event_date_wtz,event_category,event_tags,linked_assets\n";
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
        csv_data += `"${item.event_date}","${title}","${content_parsed}","${item.event_tz}","${item.event_date_wtz}","${item.category_name}","${tags}","${assets}"\n`;
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
var keywords = ['asset', 'tag', 'title', 'description', 'raw', 'category', 'source', 'startDate', 'endDate'];


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

function apply_filtering() {
    keywords = ['asset', 'tag', 'title', 'description', 'category', 'source',  'raw', 'startDate', 'endDate'];
    parsed_filter = {};
    parse_filter(tm_filter.getValue(), keywords);
    filter_query = encodeURIComponent(JSON.stringify(parsed_filter));

    $('#timeline_list').empty();
    show_loader();
     $.ajax({
        url: "/case/timeline/advanced-filter" + case_param(),
        type: "GET",
        data: { 'q': filter_query },
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                build_timeline(data);
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

function getFilterFromLink(){
    queryString = window.location.search;
    urlParams = new URLSearchParams(queryString);

    if (urlParams.get('filter') !== undefined) {
        return urlParams.get('filter')
    }
    return null;
}

function get_or_filter_tm() {
    filter = getFilterFromLink();
    if (filter) {
        tm_filter.setValue(filter);
        apply_filtering();
    } else {
        draw_timeline();
    }
}

/* Page is ready, fetch the assets of the case */
$(document).ready(function(){

    get_or_filter_tm();

    setInterval(function() { check_update('timeline/state'); }, 3000);

});

