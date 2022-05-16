function visualizeTimeline(group) {
    ggr = ['asset', 'category']
    if (group == 'asset') {
        src = '/case/timeline/visualize/data/by-asset';
    } else {
        src = '/case/timeline/visualize/data/by-category';
    }

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
                        id: index,
                        group: groups_l.indexOf(event.group),
                        start: event.date,
                        content: event.content,
                        style: event.style,
                        title: event.title
                    })

                }

              // specify options
              var options = {
                stack: true,
                minHeight: '400px',
                maxHeight: $(window).height() - 250,
                start: data.data.events[0].date,
                end: data.data.events[data.data.events.length - 1].date,
              };

              // create a Timeline

              var container = document.getElementById('visualization');
              container.innerHTML = '';
              $('#card_main_load').show();
              timeline = new vis.Timeline(container, null, options);
              if (ggr.includes(group)) {
                timeline.setGroups(groups);
              }
              timeline.setItems(items);
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