
function get_case_graph() {
    get_request_api('graph/getdata')
    .done((data) => {
            if (data.status == 'success') {
                redrawAll(data.data);
                hide_loader();
            } else {
                $('#submit_new_asset').text('Save again');
                swal("Oh no !", data.message, "error")
            }
        })
}

var network;

function redrawAll(data) {
  if (data.nodes.length == 0) {
        $('#card_main_load').show();
        $('#graph-container').text('No events in graph');
        hide_loader();
        return true;
  }
  var container = document.getElementById("graph-container");
  var options = {
    edges: {
      smooth: {
            enabled: true,
            type: 'continuous',
            roundness: 0.5
        }
    },
    layout: {
        randomSeed: 2,
        improvedLayout: true
    },
    interaction: {
      hideEdgesOnDrag: false
    },
    width: (window.innerWidth - 400) + "px",
    height: (window.innerHeight- 250) + "px",
    "physics": {
    "forceAtlas2Based": {
      "gravitationalConstant": -167,
      "centralGravity": 0.04,
      "springLength": 0,
      "springConstant": 0.02,
      "damping": 0.9
    },
    "minVelocity": 0.41,
    "solver": "forceAtlas2Based",
    "timestep": 0.45
    }
  };

  nodes = data.nodes;
  edges = data.edges;

  network = new vis.Network(container, data, options);

  network.on("stabilizationIterationsDone", function () {
        network.setOptions( { physics: false } );
    });

}


/* Page is ready, fetch the assets of the case */
$(document).ready(function(){
    get_case_graph();
});

