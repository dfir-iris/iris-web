var tm_filter = null;
var selector_active;
var current_timeline;
var g_event_id = null;
var g_event_desc_editor = null;

function edit_in_event_desc() {
    if($('#container_event_desc_content').is(':visible')) {
        $('#container_event_description').show(100);
        $('#container_event_desc_content').hide(100);
        $('#event_edition_btn').hide(100);
        $('#event_preview_button').hide(100);
    } else {
        $('#event_preview_button').show(100);
        $('#event_edition_btn').show(100);
        $('#container_event_desc_content').show(100);
        $('#container_event_description').hide(100);
    }
}

/* Fetch a modal that allows to add an event */
function add_event(parent_event_id = null) {
    url = 'timeline/events/add/modal' + case_param();
    $('#modal_add_event_content').load(url, function (response, status, xhr) {
        hide_minimized_modal_box();
        if (status !== "success") {
             ajax_notify_error(xhr, url);
             return false;
        }

        g_event_desc_editor = get_new_ace_editor('event_description', 'event_desc_content', 'target_event_desc',
                            function() {
                                $('#last_saved').addClass('btn-danger').removeClass('btn-success');
                                $('#last_saved > i').attr('class', "fa-solid fa-file-circle-exclamation");
                            }, null);

        g_event_desc_editor.setOption("minLines", "10");
        let headers = get_editor_headers('g_event_desc_editor', null, 'event_edition_btn');
        $('#event_edition_btn').append(headers);
        edit_in_event_desc();

        let parent_selector = $('#parent_event_id');

        // Add empty option
        let option = $('<option>');
        option.attr('value', '');
        option.text('No parent event');
        parent_selector.append(option);

        // Add all events to the parent selector
        for (let idx in current_timeline) {
            let event = current_timeline[idx];
            let option = $('<option>');
            option.attr('value', event.event_id);
            option.text(`${event.event_title}`);
            parent_selector.append(option);
        }

        parent_selector.selectpicker({
            liveSearch: true,
            size: 10,
            width: '100%',
            title: 'Select a parent event',
            style: 'btn-light',
            noneSelectedText: 'No event selected',
        });

        if (parent_event_id != null) {
            parent_selector.selectpicker('val', parent_event_id);
            parent_selector.selectpicker("refresh");
        }

        $('#submit_new_event').on("click", function () {
            clear_api_error();
            var data_sent = $('#form_new_event').serializeObject();
            data_sent['event_date'] = `${$('#event_date').val()}T${$('#event_time').val()}`;
            data_sent['event_in_summary'] = $('#event_in_summary').is(':checked');
            data_sent['event_in_graph'] = $('#event_in_graph').is(':checked');
            data_sent['event_sync_iocs_assets'] = $('#event_sync_iocs_assets').is(':checked');
            data_sent['event_tags'] = $('#event_tags').val();
            data_sent['event_assets'] = $('#event_assets').val();
            data_sent['event_iocs'] = $('#event_iocs').val();
            data_sent['event_tz'] = $('#event_tz').val();
            data_sent['event_content'] = g_event_desc_editor.getValue();
            data_sent['parent_event_id'] = $('#parent_event_id').val() || null;

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

        $('#modal_add_event').modal({ show: true });
        $('#event_title').focus();

    });
}

function save_event() {
    $('#submit_new_event').click();
}


function duplicate_event(id) {
    window.location.hash = id;
    clear_api_error();

    get_request_api("timeline/events/duplicate/" + id)
    .done((data) => {
        if(notify_auto_api(data)) {
            if ("data" in data && "event_id" in data.data)
            {
                window.location.hash = data.data.event_id;
            }
            apply_filtering();
        }
    });

}
function update_event(event_id) {
    update_event_ext(event_id, true);
}

function update_event_ext(event_id, do_close) {

    if (event_id === undefined || event_id === null) {
        event_id = g_event_id;
    }

    window.location.hash = event_id;
    clear_api_error();
    var data_sent = $('#form_new_event').serializeObject();
    data_sent['event_date'] = `${$('#event_date').val()}T${$('#event_time').val()}`;
    data_sent['event_in_summary'] = $('#event_in_summary').is(':checked');
    data_sent['event_in_graph'] = $('#event_in_graph').is(':checked');
    data_sent['event_sync_iocs_assets'] = $('#event_sync_iocs_assets').is(':checked');
    data_sent['event_tags'] = $('#event_tags').val();
    data_sent['event_assets'] = $('#event_assets').val();
    data_sent['event_iocs'] = $('#event_iocs').val();
    data_sent['event_tz'] = $('#event_tz').val();
    data_sent['event_content'] = g_event_desc_editor.getValue();
    data_sent['parent_event_id'] = $('#parent_event_id').val() || null;

    ret = get_custom_attributes_fields();
    has_error = ret[0].length > 0;
    attributes = ret[1];

    if (has_error){return false;}

    data_sent['custom_attributes'] = attributes;

    post_request_api('timeline/events/update/' + event_id, JSON.stringify(data_sent), true)
    .done(function(data) {
        if(notify_auto_api(data)) {
            apply_filtering();
            if (do_close !== undefined && do_close === true) {
                $('#modal_add_event').modal('hide');
            }

            $('#submit_new_event').text("Saved").addClass('btn-outline-success').removeClass('btn-outline-danger').removeClass('btn-outline-warning');
            $('#last_saved').removeClass('btn-danger').addClass('btn-success');
            $('#last_saved > i').attr('class', "fa-solid fa-file-circle-check");

        }
    });

}

/* Delete an event from the timeline thank to its id */ 
function delete_event(id) {
    window.location.hash = id;
    do_deletion_prompt("You are about to delete event #" + id)
    .then((doDelete) => {
        if (doDelete) {
            post_request_api("timeline/events/delete/" + id)
            .done(function(data) {
                if(notify_auto_api(data)) {
                    apply_filtering();
                    $('#modal_add_event').modal('hide');
                }
            });
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
        
        g_event_id = id;
        g_event_desc_editor = get_new_ace_editor('event_description', 'event_desc_content', 'target_event_desc',
                            function() {
                                $('#last_saved').addClass('btn-danger').removeClass('btn-success');
                                $('#last_saved > i').attr('class', "fa-solid fa-file-circle-exclamation");
                            }, null);
        g_event_desc_editor.setOption("minLines", "6");
        preview_event_description(true);
        headers = get_editor_headers('g_event_desc_editor', null, 'event_edition_btn');
        $('#event_edition_btn').append(headers);
        edit_in_event_desc();

        let parent_selector = $('#parent_event_id');

        // Add empty option
        let option = $('<option>');
        option.attr('value', '');
        option.text('No parent event');
        parent_selector.append(option);

        let target_idx = 0;
        // Add all events to the parent selector and remove the current event
        for (let idx in current_timeline) {
            let event = current_timeline[idx];

            if (event.event_id === id) {
                target_idx = event.parent_event_id;
                continue;
            }

            let option = $('<option>');
            option.attr('value', event.event_id);
            option.text(`${event.event_title}`);
            parent_selector.append(option);
        }

        parent_selector.selectpicker({
            liveSearch: true,
            size: 10,
            width: '100%',
            title: 'Select a parent event',
            style: 'btn-light',
            noneSelectedText: 'No event selected',
        });

        if (target_idx!= null) {
            parent_selector.selectpicker('val', target_idx);
            parent_selector.selectpicker("refresh");
        }

        load_menu_mod_options_modal(id, 'event', $("#event_modal_quick_actions"));
        $('#modal_add_event').modal({show:true});
  });
}

function preview_event_description(no_btn_update) {
    if(!$('#container_event_description').is(':visible')) {
        event_desc = g_event_desc_editor.getValue();
        converter = get_showdown_convert();
        html = converter.makeHtml(do_md_filter_xss(event_desc));
        event_desc_html = do_md_filter_xss(html);
        $('#target_event_desc').html(event_desc_html);
        $('#container_event_description').show();
        if (!no_btn_update) {
            $('#event_preview_button').html('<i class="fa-solid fa-eye-slash"></i>');
        }
        $('#container_event_desc_content').hide();
    }
    else {
        $('#container_event_description').hide();
         if (!no_btn_update) {
            $('#event_preview_button').html('<i class="fa-solid fa-eye"></i>');
        }

        $('#event_preview_button').html('<i class="fa-solid fa-eye"></i>');
        $('#container_event_desc_content').show();
    }
}

function is_timeline_compact_view() {
    var x = localStorage.getItem('iris-tm-compact');
    if (typeof x !== 'undefined') {
        if (x === 'true') {
            return true;
        }
    }
    return false;
}

function toggle_compact_view() {
    var x = localStorage.getItem('iris-tm-compact');
    if (typeof x === 'undefined') {
        localStorage.setItem('iris-tm-compact', 'true');
        location.reload();
    } else {
        if (x === 'true') {
            localStorage.setItem('iris-tm-compact', 'false');
            location.reload();
        } else {
             localStorage.setItem('iris-tm-compact', 'true');
            location.reload();
        }
    }
}


function is_timeline_tree_view() {
    var x = localStorage.getItem('iris-tm-tree');
    if (typeof x !== 'undefined') {
        if (x === 'true') {
            return true;
        }
    }
    return false;
}


function toggle_tree_view() {
    var x = localStorage.getItem('iris-tm-tree');
    if (typeof x === 'undefined') {
        localStorage.setItem('iris-tm-tree', 'true');
        location.reload();
    } else {
        if (x === 'true') {
            localStorage.setItem('iris-tm-tree', 'false');
            location.reload();
        } else {
             localStorage.setItem('iris-tm-tree', 'true');
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

        $(".timeline li .timeline-panel-t").on('click', function(){
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
                if(attribute === 'event_in_graph' || attribute === 'event_in_summary'){
                    attribute_value = original_event[attribute];
                    original_event[attribute] = !attribute_value;
                } else if(attribute === 'event_color') {
                    // attribute value already set to color L240
                    original_event[attribute] = attribute_value;
                }

                //add csrf token to request
                original_event['csrf_token'] = $("#csrf_token").val();
                delete original_event['event_comments_map'];

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
                post_request_api("timeline/events/delete/" + event_id)
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

function toggleSeeMore(element) {
    let ariaExpanded = element.getAttribute('aria-expanded');
    if (ariaExpanded === 'false') {
        element.innerHTML = '&gt; See less';
    } else {
        element.innerHTML = '&gt; See more';
    }
}

function buildEvent(event_data, compact, comments_map, tree, tesk, tmb, idx, reap, converter) {
    let evt = event_data;
    let dta =  evt.event_date.toString().split('T');
    let tags = '';
    let cats = '';
    let tmb_d = '';
    let style = '';
    let asset = '';

    if (evt.event_id in comments_map) {
        nb_comments = comments_map[evt.event_id].length;
    } else {
        nb_comments = '';
    }

    if(evt.category_name && evt.category_name != 'Unspecified') {
         if (!compact) {
             tags += `<span class="badge badge-light float-right ml-1 mt-2">${sanitizeHTML(evt.category_name)}</span>`;
         } else {
             if (evt.category_name != 'Unspecified') {
                 cats += `<span class="badge badge-light float-right ml-1 mt-1 mr-2 mb-1">${sanitizeHTML(evt.category_name)}</span>`;
             }
         }
    }

    if (evt.iocs != null && evt.iocs.length > 0) {
        for (let ioc in evt.iocs) {
            let span_anchor = $('<span>');
            span_anchor.addClass('badge badge-warning-event float-right ml-1 mt-2');
            span_anchor.attr('data-toggle', 'popover');
            span_anchor.attr('data-trigger', 'hover');
            span_anchor.attr('style', 'cursor: pointer;');
            span_anchor.attr('data-content', 'IOC - ' + evt.iocs[ioc].description);
            span_anchor.attr('title', evt.iocs[ioc].name);
            span_anchor.text(evt.iocs[ioc].name)
            span_anchor.html('<i class="fa-solid fa-virus-covid mr-1"></i>' + span_anchor.html());
            tags += span_anchor[0].outerHTML;
        }
    }

    if (evt.event_tags != null && evt.event_tags.length > 0) {
        sp_tag = evt.event_tags.split(',');
        for (tag_i in sp_tag) {
                tags += get_tag_from_data(sp_tag[tag_i], 'badge badge-light ml-1 float-right mt-2');
            }
    }

    let entry = '';
    let inverted = 'timeline';
    let timeline_style = tree ? '-t' : '';

    /* Do we have a border color to set ? */
    if (tesk) {
        style += "timeline-odd"+ timeline_style;
        tesk = false;
    } else {
        style += "timeline-even" + timeline_style;
        tesk = true;
    }

    let style_s = "";
    if (evt.event_color != null) {
            style_s = `style='border-left: 2px groove ${sanitizeHTML(evt.event_color)};'`;
    }

    if (!tree) {
        inverted += '-inverted';
    } else {
        if (tesk) {
            inverted += '-inverted';
        }
    }


    /* For every assets linked to the event, build a link tag */
    if (evt.assets != null) {
        for (let ide in evt.assets) {
            let cpn =  evt.assets[ide]["ip"] + ' - ' + evt.assets[ide]["description"]
            cpn = sanitizeHTML(cpn)
            let span_anchor = $('<span>');
            span_anchor.attr('data-toggle', 'popover');
            span_anchor.attr('data-trigger', 'hover');
            span_anchor.attr('style', 'cursor: pointer;');
            span_anchor.attr('data-content', cpn);
            span_anchor.attr('title', evt.assets[ide]["name"]);
            span_anchor.text(evt.assets[ide]["name"]);

            if (evt.assets[ide]["compromised"]) {
                span_anchor.addClass('badge badge-warning-event float-right ml-1 mt-2');
            } else {
                span_anchor.addClass('badge badge-light float-right ml-1 mt-2');
            }

            asset += span_anchor[0].outerHTML;
        }
    }

    let ori_date = '<span class="ml-3"></span>';
    if (evt.event_date_wtz != evt.event_date) {
        ori_date += `<i class="fas fa-info-circle mr-1" title="Locale date time ${evt.event_date_wtz}${evt.event_tz}"></i>`
    }

    if(evt.event_in_summary) {
        ori_date += `<i class="fas fa-newspaper mr-1" title="Showed in summary"></i>`
    }

    if(evt.event_in_graph) {
        ori_date += `<i class="fas fa-share-alt mr-1" title="Showed in graph"></i>`
    }


    let day = dta[0];
    // Transform the date to the user's system format. day is in the format YYYY-MM-DD. We want our date in the user's host format, without the minutes and seconds.
    // First parse the date to a Date object
    let date = new Date(day);
    // Then use the toLocaleDateString method to get the date in the user's host format
    day = date.toLocaleDateString();

    let hour = dta[1].split('.')[0];

    let mtop_day = '';

    if (!tmb.includes(day) && evt.parent_event_id == null) {
        tmb.push(day);
        tmb_d = `<li class="time-badge${timeline_style} badge badge-dark" id="time_${idx}"><small class="">${day}</small><br/></li>`;

        idx += 1;
        mtop_day = 'mt-4';
    }

    let title_parsed = match_replace_ioc(sanitizeHTML(evt.event_title), reap);
    let raw_content = do_md_filter_xss(evt.event_content); // Raw markdown content
    let formatted_content = converter.makeHtml(raw_content); // Convert markdown to HTML

    const wordLimit = 30; // Define your word limit

    if (!compact) {
        let paragraphs = raw_content.split('\n\n');
        let short_content, long_content;

        if (paragraphs.join(' ').split(' ').length > wordLimit || paragraphs.length > 2) {
            let temp_content = '';
            let i = 0;
            let wordCount = 0;

            // Loop until the content length is more than wordLimit or paragraph count is more than 2
            while(wordCount <= wordLimit && i < 2 && i < paragraphs.length){
                let words = paragraphs[i].split(' ');
                if (wordCount + words.length > wordLimit && wordCount != 0) {
                    break;
                }
                temp_content += paragraphs[i] + '\n\n';
                wordCount += words.length;
                i++;
            }

            short_content = converter.makeHtml(temp_content); // Convert markdown to HTML
            short_content = match_replace_ioc(filterXSS(short_content), reap);
            temp_content = paragraphs.slice(i).join('\n\n');
            long_content = converter.makeHtml(temp_content); // Convert markdown to HTML
            long_content = match_replace_ioc(filterXSS(long_content), reap);

            formatted_content = short_content + `<div class="collapse" id="collapseContent-${evt.event_id}">
            ${long_content}
            </div>
            <a class="btn btn-link btn-sm" data-toggle="collapse" href="#collapseContent-${evt.event_id}" role="button" aria-expanded="false" aria-controls="collapseContent" onclick="toggleSeeMore(this)">&gt; See more</a>`;
        } else {
            let content_parsed = converter.makeHtml(raw_content); // Convert markdown to HTML
            content_parsed = filterXSS(content_parsed);
            formatted_content = match_replace_ioc(content_parsed, reap);
        }
    }

    let shared_link = buildShareLink(evt.event_id);

    let flag = '';
    if (evt.event_is_flagged) {
        flag = `<i class="fas fa-flag text-warning" title="Flagged"></i>`;
    } else {
        flag = `<i class="fa-regular fa-flag" title="Not flagged"></i>`;
    }

    if (compact) {
        entry = `<li class="${inverted} ${mtop_day}" title="Event ID #${evt.event_id}" data-datetime="${evt.event_date}" >
                <div class="timeline-panel${timeline_style} ${style}" ${style_s}  id="event_${evt.event_id}">
                    <div class="timeline-heading">
                        <div class="btn-group dropdown float-right">
                            ${cats}
                            <button type="button" class="btn btn-light btn-xs" onclick="edit_event(${evt.event_id})" title="Edit">
                                <span class="btn-label">
                                    <i class="fa fa-pen"></i>
                                </span>
                            </button>
                            <button type="button" class="btn btn-light btn-xs" onclick="flag_event(${evt.event_id})" title="Flag">
                                <span class="btn-label">
                                    ${flag}
                                </span>
                            </button>
                            <button type="button" class="btn btn-light btn-xs" onclick="comment_element(${evt.event_id}, 'timeline/events')" title="Comments">
                                <span class="btn-label">
                                    <i class="fa-solid fa-comments"></i><span class="notification" id="object_comments_number_${evt.event_id}">${nb_comments}</span>
                                </span>
                            </button>
                            <button type="button" class="btn btn-light btn-xs dropdown-toggle" data-toggle="dropdown" aria-expanded="false">
                                <span class="btn-label">
                                    <i class="fa fa-cog"></i>
                                </span>
                            </button>
                            <div class="dropdown-menu" role="menu" x-placement="bottom-start" style="position: absolute; transform: translate3d(0px, 32px, 0px); top: 0px; left: 0px; will-change: transform;">
                                    <a href= "#" class="dropdown-item" onclick="copy_object_link(${evt.event_id});return false;"><small class="fa fa-share mr-2"></small>Share</a>
                                    <a href= "#" class="dropdown-item" onclick="copy_object_link_md('event', ${evt.event_id});return false;"><small class="fa-brands fa-markdown mr-2"></small>Markdown Link</a>
                                    <a href= "#" class="dropdown-item" onclick="duplicate_event(${evt.event_id});return false;"><small class="fa fa-clone mr-2"></small>Duplicate</a>
                                    <div class="dropdown-divider"></div>
                                    <a href= "#" class="dropdown-item text-danger" onclick="delete_event(${evt.event_id});"><small class="fa fa-trash mr-2"></small>Delete</a>
                            </div>
                        </div>
                        <div class="collapsed" id="dropa_${evt.event_id}" data-toggle="collapse" data-target="#drop_${evt.event_id}" aria-expanded="false" aria-controls="drop_${evt.event_id}" role="button" style="cursor: pointer;">
                            <span class="text-muted text-sm float-left mb--2"><small>${formatTime(evt.event_date, { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'})}</small></span>
                            <a class="text-dark text-sm ml-3" href="${shared_link}" onclick="edit_event(${evt.event_id});return false;">${title_parsed}</a>
                        </div>
                    </div>
                    <div class="timeline-body text-faded" >
                        <div id="drop_${evt.event_id}" class="collapse" aria-labelledby="dropa_${evt.event_id}" style="">
                            <div class="card-body">
                            ${formatted_content}
                            </div>
                            <div class="bottom-hour mt-2">
                                <span class="float-right">${tags}${asset} </span>
                            </div>
                        </div>
                    </div>
                </div>
            </li>`
    } else {
        entry = `<li class=${inverted} title="Event ID #${evt.event_id}" >
                <div class="timeline-panel${timeline_style} ${style}" ${style_s} id="event_${evt.event_id}">
                    <div class="timeline-heading">
                        <div class="btn-group dropdown float-right">

                            <button type="button" class="btn btn-light btn-xs" onclick="edit_event(${evt.event_id})" title="Edit">
                                <span class="btn-label">
                                    <i class="fa fa-pen"></i>
                                </span>
                            </button>
                            <button type="button" class="btn btn-light btn-xs" onclick="add_event(${evt.event_id})" title="Add child event">
                                <span class="btn-label">
                                   <i class="fa-brands fa-hive"></i>
                                </span>
                            </button>
                            <button type="button" class="btn btn-light btn-xs" onclick="flag_event(${evt.event_id})" title="Flag">
                                <span class="btn-label">
                                    ${flag}
                                </span>
                            </button>
                            <button type="button" class="btn btn-light btn-xs" onclick="comment_element(${evt.event_id}, 'timeline/events')" title="Comments">
                                <span class="btn-label">
                                    <i class="fa-solid fa-comments"></i><span class="notification" id="object_comments_number_${evt.event_id}">${nb_comments}</span>
                                </span>
                            </button>
                            <button type="button" class="btn btn-light btn-xs dropdown-toggle" data-toggle="dropdown" aria-expanded="false">
                                <span class="btn-label">
                                    <i class="fa fa-cog"></i>
                                </span>
                            </button>
                            <div class="dropdown-menu" role="menu" x-placement="bottom-start" style="position: absolute; transform: translate3d(0px, 32px, 0px); top: 0px; left: 0px; will-change: transform;">
                                    <a href= "#" class="dropdown-item" onclick="copy_object_link(${evt.event_id});return false;"><small class="fa fa-share mr-2"></small>Share</a>
                                    <a href= "#" class="dropdown-item" onclick="copy_object_link_md('event', ${evt.event_id});return false;"><small class="fa-brands fa-markdown mr-2"></small>Markdown Link</a>
                                    <a href= "#" class="dropdown-item" onclick="duplicate_event(${evt.event_id});return false;"><small class="fa fa-clone mr-2"></small>Duplicate</a>
                                    <div class="dropdown-divider"></div>
                                    <a href= "#" class="dropdown-item text-danger" onclick="delete_event(${evt.event_id});"><small class="fa fa-trash mr-2"></small>Delete</a>
                            </div>
                        </div>
                        <div class="row mb-2">
                            <a class="timeline-title" href="${shared_link}" onclick="edit_event(${evt.event_id});return false;">[${hour}] ${title_parsed}</a>
                        </div>
                    </div>
                    <div class="timeline-body text-faded" >
                        <span>${formatted_content}</span>

                        <div class="bottom-hour mt-2">
                            <div class="row">
                                <div class="col d-flex">
                                    <span class="text-muted text-sm align-self-end float-left mb--2"><small class="bottom-hour-i"><i class="flaticon-stopwatch mr-2"></i>${formatTime(evt.event_date, { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'})}${ori_date}</small></span>
                                </div>
                                
                                <div class="col">
                                    <span class="float-right">${tags}${asset} </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </li>`
    }
    return [entry, tmb_d];
}

function build_timeline(data) {
    let compact = is_timeline_compact_view();
    let tree = is_timeline_tree_view();
    var is_i = false;
    current_timeline = data.data.tim;
    let tmb = [];

    let reid = 0;

    $('#time_timeline_select').empty();

    var standard_filters = [
                {value: 'asset:', score: 10, meta: 'Match assets name of events'},
                {value: 'asset_id:', score: 10, meta: 'Match assets ID of events'},
                {value: 'startDate:', score: 10, meta: 'Match end date of events'},
                {value: 'endDate:', score: 10, meta: 'Match end date of events'},
                {value: 'tag:', score: 10, meta: 'Match tag of events'},
                {value: 'description:', score: 10, meta: 'Match description of events'},
                {value: 'flag', score: 10, meta: 'Match flagged events'},
                {value: 'category:', score: 10, meta: 'Match category of events'},
                {value: 'title:', score: 10, meta: 'Match title of events'},
                {value: 'source:', score: 10, meta: 'Match source of events'},
                {value: 'raw:', score: 10, meta: 'Match raw data of events'},
                {value: 'ioc', score: 10, meta: "Match ioc value in events"},
                {value: 'ioc_id', score: 10, meta: "Match ioc ID in events"},
                {value: 'event_id', score: 10, meta: "Match event ID in events"},
                {value: 'AND ', score: 10, meta: 'AND operator'}
              ]

    for (let rid in data.data.assets) {
        standard_filters.push(
             {value: data.data.assets[rid][0], score: 1, meta: data.data.assets[rid][1]}
        );
    }

    for (let rid in data.data.categories) {
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

    let tesk = false;
    let reap = [];
    let ioc_list = data.data.iocs;
    for (ioc in ioc_list) {
        let ioc_len = ioc_list[ioc]['ioc_value'].length;
        if (ioc_len === 0 || ioc_len > 64) {
            console.log('Ignoring IOC with length 0 or > 64')
            continue;
        }
        let capture_start = "(^|;|:|||>|<|[|]|(|)|\s|\>)(";
        let capture_end = ")(;|:|||>|<|[|]|(|)|\s|>|$|<br/>)";
        // When an IOC contains another IOC in its description, we want to avoid to replace that particular pattern
        var avoid_inception_start = "(?!<span[^>]*?>)" + capture_start;
        var avoid_inception_end = "(?![^<]*?<\/span>)" + capture_end;
        var re = new RegExp(avoid_inception_start
               + escapeRegExp(sanitizeHTML(ioc_list[ioc]['ioc_value']))
               + avoid_inception_end
               ,"g");
        let replacement = `$1<span class="text-warning-high ml-1 link_asset" data-toggle="popover" style="cursor: pointer;" data-trigger="hover" data-content="${sanitizeHTML(ioc_list[ioc]['ioc_description'])}" title="IOC">${sanitizeHTML(ioc_list[ioc]['ioc_value'])}</span>`;
        reap.push([re, replacement]);
    }
    let idx = 0;

    let converter = get_showdown_convert();
    let child_events = Object();

    for (let index in data.data.tim) {
        let evt =  data.data.tim[index];
        let eki = buildEvent(evt, compact, data.data.comments_map, tree, tesk, tmb, idx, reap, converter);
        tesk = !tesk;

        is_i = false;
        let entry = eki[0];
        let tmb_d = eki[1];

        if (evt.parent_event_id != null) {
            if (!(evt.parent_event_id in child_events)) {
                child_events[evt.parent_event_id] = [];
            }
            child_events[evt.parent_event_id].push(entry);
            tesk = !tesk;

        } else {
            $('#timeline_list').append(tmb_d);
            $('#timeline_list').append(entry);
        }

    }


    if (tree) {
        $('#timeline_list').addClass('timeline-t');
    } else {
        $('#timeline_list').removeClass('timeline-t');
    }

    for (let parent_id in child_events) {
        let parent_event = $('#event_' + parent_id);

        let parent_event_class = parent_event.parent().attr('class');
        let parent_class = parent_event.attr('class');

        // Reverse the order of the child events list
        child_events[parent_id] = child_events[parent_id].reverse();

        // Add button on parent to toggle child events
        let button = $('<button>');
        button.attr('type', 'button');
        button.attr('class', 'btn btn-light btn-xs mt-2');
        button.attr('onclick', `toggle_child_events_of_event(${parent_id});`);
        button.attr('title', 'Toggle child events');
        button.html('<span class="btn-label"><i class="fa fa-chevron-down"></i></span>');

        parent_event.find('.timeline-body').append(button);

        for (let child_html in child_events[parent_id]) {

            let child = $(child_events[parent_id][child_html]);

            child.attr('class', parent_event_class);
            child.addClass('timeline-child');
            child.addClass('timeline-child-' + parent_id);

            child.find('div:first').attr('class', parent_class);

            let child_date = child.find('.bottom-hour').find('small').text();
            let parent_date = parent_event.find('.bottom-hour').find('small').text();
            child_date = Date.parse(child_date);
            parent_date = Date.parse(parent_date);

            if (child_date < parent_date) {
                child.find('.bottom-hour-i').append('<span class="ml-2"><i class="fas fa-exclamation-triangle text-warning" title="Child event datetime is earlier than parent event"></i></span>')
            }

            child.insertAfter(parent_event.parent());
        }

    }

    //match_replace_ioc(data.data.iocs, "timeline_list");
    $('[data-toggle="popover"]').popover();

    if (data.data.tim.length === 0) {
       $('#card_main_load').append('<h3 class="ml-mr-auto text-center" id="no_events_msg">No events in current view</h3>');
       $('#timeline_list').hide();
    } else {
        $('#timeline_list').show();
        $('#no_events_msg').remove('h3');
    }

    set_last_state(data.data.state);
    hide_loader();

    if (location.href.indexOf("#") != -1) {
        var current_url = window.location.href;
        var id = current_url.substr(current_url.indexOf("#") + 1);
        if ($('#event_'+id).offset() != undefined) {
            $('.content').animate({ scrollTop: $('#event_'+id).offset().top - 180 });
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

function toggle_child_events() {
    let child_events = $('.timeline-child');
    if (child_events.is(':visible')) {
        child_events.hide();
        // Find the button of the parent event, excluding the child events themselves
        for (let i = 0; i < child_events.length; i++) {
            let child_event = child_events[i];
            let parent_event = $(child_event).prev();
            if (parent_event.hasClass('timeline-child')) {
                continue;
            }
            let btn = parent_event.find('button:last');
            if (btn.html().indexOf('fa-chevron-down') !== -1) {
                btn.html('<span class="btn-label"><i class="fa fa-chevron-right"></i> Child events</span>');
            }
        }


    } else {
        child_events.show();
        for (let i = 0; i < child_events.length; i++) {
            let child_event = child_events[i];
            let parent_event = $(child_event).prev();
            if (parent_event.hasClass('timeline-child')) {
                continue;
            }
            let btn = parent_event.find('button:last');
            if (btn.html().indexOf('fa-chevron-right') !== -1) {
                btn.html('<span class="btn-label"><i class="fa fa-chevron-down"></i></span>');
            }
        }
    }
}

function toggle_child_events_of_event(event_id) {
    let child_events = $('.timeline-child-' + event_id);
    let event = $('#event_' + event_id);

    if (child_events.is(':visible')) {
        child_events.hide();
        let btn = $('#event_' + event_id).find('button:last');
        if (btn.html().indexOf('fa-chevron-down') !== -1) {
            btn.html('<span class="btn-label"><i class="fa fa-chevron-right"></i> Child events</span>');
        }
    } else {
        child_events.show();
        let btn = $('#event_' + event_id).find('button:last');
        if (btn.html().indexOf('fa-chevron-right') !== -1) {
            btn.html('<span class="btn-label"><i class="fa fa-chevron-down"></i></span>');
        }
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
    // Get last element ID of the timeline
    let last_element_id = $('.timeline li:last > div').attr('id').replace('event_', '');

    // Scroll to the last element
    $('html').animate({ scrollTop: $('#event_'+last_element_id).offset().top - 80 });
}

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

function flag_event(event_id){
    get_request_api('timeline/events/flag/'+event_id)
    .done(function(data) {
        if (notify_auto_api(data)) {
            uiFlagEvent(event_id, data.data.event_is_flagged)
        }
    });
}

function uiFlagEvent(event_id, is_flagged) {
    if (is_flagged === true) {
        $('#event_'+event_id).find('.fa-flag').addClass('fas text-warning').removeClass('fa-regular');
    } else {
        $('#event_'+event_id).find('.fa-flag').addClass('fa-regular').removeClass('fas text-warning');
    }
}

function uiRemoveEvent(event_id) {
    $('#event_'+event_id).remove();
}

function uiUpdateEvent(event_id, event_data) {
    let last_event_id = 0;
    for (let index in current_timeline){
        let list_date = new Date(current_timeline[index].event_date);
        let evt_date = new Date(event_data.event_date);

        if (list_date < evt_date) {
            last_event_id = current_timeline[index].event_id;
        }
    }
    if (last_event_id !== 0) {
        let updated_event = $(`#event_${event_id}`).html();
        $(`#event_${event_id}`).remove();
        $(`#event_${last_event_id}`).after(updated_event);
    }
}

function time_converter(){
    let date_val = $('#event_date_convert_input').val();

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

let parsed_filter = {};
let keywords = ['asset', 'asset_id', 'tag', 'title', 'description', 'ioc', 'ioc_id',
        'raw', 'category', 'source', 'flag', 'startDate', 'endDate', 'event_id'];

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
    keywords = ['asset', 'asset_id', 'tag', 'title', 'description', 'ioc', 'ioc_id',
        'raw', 'category', 'source', 'flag', 'startDate', 'endDate', 'event_id'];

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

function show_timeline_filter_help() {
    $('#modal_help').load('/case/timeline/filter-help/modal' + case_param(), function (response, status, xhr) {
        if (status !== "success") {
             ajax_notify_error(xhr, '/case/timeline/filter-help/modal');
             return false;
        }
        $('#modal_help').modal('show');
    });
}

/* BEGIN_RS_CODE */
function fire_upload_csv_events() {
    $('#modal_upload_csv_events').modal('show');
}

function upload_csv_events() {
    const api_path =  '/case/timeline/events/csv_upload';
    const modal_dlg = '#modal_upload_csv_events'
    const file_input = '#input_upload_csv_events'

    var file = $(file_input).get(0).files[0];

    var reader = new FileReader();
    reader.onload = function (e) {
        let fileData = e.target.result
        let data = new Object();
        data['csrf_token'] = $('#csrf_token').val();
        data['CSVData'] = fileData;

        post_request_api(api_path, JSON.stringify(data), true)
        .done((data) => {

            if (notify_auto_api(data)) {
                apply_filtering();
                $(modal_dlg).modal('hide');
                swal("Got news for you", data.message, "success");
            } else {
                //alert( JSON.stringify(data.data,null,2));
                swal("Got bad news for you", data.message, "error");
            }
        })

    };
    reader.readAsText(file)

    return false;
}

function handleCollabNotifications(collab_data) {
   if (collab_data.action_type === "flagged") {
       uiFlagEvent(collab_data.object_id, true);
   }
   else if (collab_data.action_type === "un-flagged") {
       uiFlagEvent(collab_data.object_id, false);
   }
   else if (collab_data.action_type === "deletion") {
       uiRemoveEvent(collab_data.object_id);
   }
   // else if (collab_data.action_type === 'updated') {
   //     uiUpdateEvent(collab_data.object_id,
   //         collab_data.object_data)
   // }
}

function generate_events_sample_csv(){
    csv_data = "event_date,event_tz,event_title,event_category,event_content,event_raw,event_source,event_assets,event_iocs,event_tags\n"
    csv_data += '"2023-03-26T03:00:30.000","+00:00","An event","Unspecified","Event description","raw","source","","","defender|malicious"\n'
    csv_data += '"2023-03-26T03:00:35.000","+00:00","An event","Legitimate","Event description","raw","source","","","defender|malicious"\n'
    download_file("sample_events.csv", "text/csv", csv_data);
}

/* END_RS_CODE */

/* Page is ready, fetch the assets of the case */
$(document).ready(function(){

    selector_active = false;

    tm_filter = ace.edit("timeline_filtering",
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
    $('#time_timeline_select').on('change', function(e){
        id = $('#time_timeline_select').val();
        $('html, body').animate({ scrollTop: $('#time_'+id).offset().top - 180 });
    });

    get_or_filter_tm();

    setInterval(function() { check_update('timeline/state'); }, 3000);

    collab_case.on('case-obj-notif', function(data) {
        let js_data = JSON.parse(data);
        if (js_data.object_type === 'events') {
            handleCollabNotifications(js_data);
        }
    });

});

