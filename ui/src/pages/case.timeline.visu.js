var timeline = null;
var timeline_items = null;
var g_event_id = null;
var g_event_desc_editor = null;
var current_timeline = [];
var current_visualization_group = null;

function get_visualization_state_key() {
    return `timeline.visualization.state:${get_caseid()}`;
}

function get_visualization_state() {
    try {
        const raw_state = localStorage.getItem(get_visualization_state_key());
        if (!raw_state) {
            return null;
        }

        return JSON.parse(raw_state);
    } catch (error) {
        return null;
    }
}

function save_visualization_state() {
    if (!timeline) {
        return;
    }

    try {
        const window_data = timeline.getWindow();
        const state = {
            start: window_data.start.toISOString(),
            end: window_data.end.toISOString(),
            group: current_visualization_group
        };
        localStorage.setItem(get_visualization_state_key(), JSON.stringify(state));
    } catch (error) {
        // Ignore storage failures (private mode/quota), timeline still works without persistence.
    }
}

function clear_visualization_state() {
    try {
        localStorage.removeItem(get_visualization_state_key());
    } catch (error) {
        // Ignore storage failures.
    }
}

function get_timeline_events_cache(callback) {
    get_request_api('/case/timeline/events/list')
    .done((data) => {
        if (data.status === 'success' && data.data && data.data.timeline) {
            current_timeline = data.data.timeline;
        } else {
            current_timeline = [];
        }

        if (callback) {
            callback();
        }
    });
}

function edit_in_event_desc() {
    if ($('#container_event_desc_content').is(':visible')) {
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

function preview_event_description(no_btn_update) {
    if (!$('#container_event_description').is(':visible')) {
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
    } else {
        $('#container_event_description').hide();
        if (!no_btn_update) {
            $('#event_preview_button').html('<i class="fa-solid fa-eye"></i>');
        }

        $('#event_preview_button').html('<i class="fa-solid fa-eye"></i>');
        $('#container_event_desc_content').show();
    }
}

function show_time_converter() {
    $('#event_date_convert').show();
    $('#event_date_convert_input').focus();
    $('#event_date_inputs').hide();
}

function hide_time_converter() {
    $('#event_date_convert').hide();
    $('#event_date_inputs').show();
    $('#event_date').focus();
}

function time_converter() {
    let date_val = $('#event_date_convert_input').val();

    var data_sent = Object();
    data_sent['date_value'] = date_val;
    data_sent['csrf_token'] = $('#csrf_token').val();

    post_request_api('/case/timeline/events/convert-date', JSON.stringify(data_sent))
    .done(function(data) {
        if (notify_auto_api(data)) {
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

function duplicate_event(id) {
    window.location.hash = id;
    clear_api_error();

    get_request_api(`/case/timeline/events/duplicate/${id}`)
    .done((data) => {
        if (notify_auto_api(data)) {
            refresh_timeline_graph();
        }
    });
}

function delete_event(id) {
    window.location.hash = id;
    do_deletion_prompt("You are about to delete event #" + id)
    .then((doDelete) => {
        if (doDelete) {
            post_request_api(`/case/timeline/events/delete/${id}`)
            .done(function(data) {
                if (notify_auto_api(data)) {
                    refresh_timeline_graph();
                    $('#modal_add_event').modal('hide');
                }
            });
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

    if (has_error) {
        return false;
    }

    data_sent['custom_attributes'] = attributes;

    post_request_api(`/case/timeline/events/update/${event_id}`, JSON.stringify(data_sent), true)
    .done(function(data) {
        if (notify_auto_api(data)) {
            refresh_timeline_graph();

            if (do_close !== undefined && do_close === true) {
                $('#modal_add_event').modal('hide');
            }

            $('#submit_new_event').text("Saved").addClass('btn-outline-success').removeClass('btn-outline-danger').removeClass('btn-outline-warning');
            $('#last_saved').removeClass('btn-danger').addClass('btn-success');
            $('#last_saved > i').attr('class', "fa-solid fa-file-circle-check");
        }
    });
}

function edit_event(id) {
    const url = '/case/timeline/events/' + id + '/modal' + case_param();
    window.location.hash = id;

    $('#modal_add_event_content').load(url, function(response, status, xhr) {
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

        get_timeline_events_cache(function() {
            let parent_selector = $('#parent_event_id');

            // Add empty option
            let option = $('<option>');
            option.attr('value', '');
            option.text('No parent event');
            parent_selector.append(option);

            let target_idx = null;
            // Add all events to the parent selector and remove the current event
            for (let idx in current_timeline) {
                let event = current_timeline[idx];

                if (event.event_id === id) {
                    target_idx = event.parent_event_id;
                    continue;
                }

                let selector_option = $('<option>');
                selector_option.attr('value', event.event_id);
                selector_option.text(`${event.event_title}`);
                parent_selector.append(selector_option);
            }

            parent_selector.selectpicker({
                liveSearch: true,
                size: 10,
                width: '100%',
                title: 'Select a parent event',
                style: 'btn-light',
                noneSelectedText: 'No event selected',
            });

            if (target_idx !== null) {
                parent_selector.selectpicker('val', target_idx);
                parent_selector.selectpicker("refresh");
            }

            load_menu_mod_options_modal(id, 'event', $("#event_modal_quick_actions"));
            $('#modal_add_event').modal({ show: true });
        });
    });
}

function setup_visualization_click_handler() {
    if (!timeline || !timeline_items) {
        return;
    }

    timeline.on('select', function(properties) {
        if (!properties.items || properties.items.length === 0) {
            return;
        }

        const selected_item = timeline_items.get(properties.items[0]);
        if (!selected_item || !selected_item.event_id) {
            return;
        }

        edit_event(selected_item.event_id);
    });
}

function setup_visualization_range_handler() {
    if (!timeline) {
        return;
    }

    timeline.on('rangechanged', function(properties) {
        if (properties.byUser) {
            save_visualization_state();
        }
    });
}

function visualizeTimeline(group) {
    current_visualization_group = group || null;
    const groupedModes = ['ioc', 'asset', 'color', 'tag', 'category'];
    const groupToEndpoint = {
        ioc: '/case/timeline/visualize/data/by-ioc',
        asset: '/case/timeline/visualize/data/by-asset',
        color: '/case/timeline/visualize/data/by-color',
        tag: '/case/timeline/visualize/data/by-tag',
        category: '/case/timeline/visualize/data/by-category'
    };
    const src = groupToEndpoint[group] || groupToEndpoint.category;

    get_request_api(src)
    .done((data) => {
        if (data.status == 'success') {
              var items = new vis.DataSet();

              groups = new vis.DataSet();
              groups_l = []
              if (data.data.events.length == 0) {
                    $('#card_main_load').show();
                    $('#visualization').text('No events in summary');
                    hide_loader();
                    return true;
              }
              for (index in data.data.events) {
                    event = data.data.events[index];
                    if (!groups_l.includes(event.group)){
                        groups.add({
                            id: groups_l.length,
                            content: event.group
                        })
                        groups_l.push(event.group);
                    }
                    items.add({
                        id: `${event.unique_id}-${index}`,
                        event_id: event.unique_id,
                        group: groups_l.indexOf(event.group),
                        start: event.date,
                        content: event.content,
                        style: event.style,
                        title: event.title
                    })

                }

              // specify options
              const state = get_visualization_state();
              var options = {
                stack: true,
                minHeight: '400px',
                maxHeight: $(window).height() - 250,
                start: state && state.start ? state.start : data.data.events[0].date,
                end: state && state.end ? state.end : data.data.events[data.data.events.length - 1].date,
              };

              // create a Timeline

              var container = document.getElementById('visualization');
              container.innerHTML = '';
              $('#card_main_load').show();
              timeline = new vis.Timeline(container, null, options);
              if (groupedModes.includes(group)) {
                timeline.setGroups(groups);
              }
              timeline.setItems(items);
              timeline_items = items;
              setup_visualization_click_handler();
              setup_visualization_range_handler();
              hide_loader();

        }
    });
}

function refresh_timeline_graph(){
    show_loader();
    queryString = window.location.search;
    urlParams = new URLSearchParams(queryString);
    group = urlParams.get('group-by');
    visualizeTimeline(group);
}

function reset_timeline_graph() {
    clear_visualization_state();

    const url = new URL(window.location.href);
    url.searchParams.delete('group-by');
    url.hash = '';

    const query_string = url.searchParams.toString();
    window.location.href = query_string ? `${url.pathname}?${query_string}` : url.pathname;
}

$(document).ready(function() {
    $('#modal_add_event').off('hidden.bs.modal.visu').on('hidden.bs.modal.visu', function() {
        refresh_timeline_graph();
    });
});
