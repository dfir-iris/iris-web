
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
var graphNodes;
var graphEdges;
var graphNodeDefaults;
var NODE_DEFAULT_SIZE = 25;
var NODE_HIGHLIGHT_SIZE = 40;
var EDGE_DEFAULT_WIDTH = 1;
var EDGE_HIGHLIGHT_WIDTH = 2;

function getNodeFontColor(baseFont) {
  if (typeof baseFont === 'string') {
    const lower = baseFont.toLowerCase();
    if (lower.includes('white')) {
      return '#ffffff';
    }
    if (lower.includes('black')) {
      return '#111111';
    }
  }

  if (baseFont && typeof baseFont === 'object' && baseFont.color) {
    return baseFont.color;
  }

  return '#111111';
}

function getNodeFontFace(baseFont) {
  if (baseFont && typeof baseFont === 'object' && baseFont.face) {
    return baseFont.face;
  }

  return 'verdana';
}

function buildHighlightFont(baseFont) {
  const baseColor = getNodeFontColor(baseFont);
  const isLightColor = baseColor.toLowerCase() === '#ffffff' || baseColor.toLowerCase() === 'white';

  return {
    color: baseColor,
    face: getNodeFontFace(baseFont),
    size: 18,
    strokeWidth: isLightColor ? 4 : 3,
    strokeColor: isLightColor ? '#000000' : '#ffffff'
  };
}

function selectLinkedNodes(nodeId) {
  const connectedNodes = network.getConnectedNodes(nodeId);
  const connectedEdges = network.getConnectedEdges(nodeId);

  applyGraphHighlight([...new Set([nodeId, ...connectedNodes])], connectedEdges);
}

function selectEdgeEndpoints(edgeIds) {
  const connectedNodes = [];

  edgeIds.forEach((edgeId) => {
    const edge = graphEdges.get(edgeId);
    if (!edge) {
      return;
    }

    connectedNodes.push(edge.from, edge.to);
  });

  applyGraphHighlight([...new Set(connectedNodes)], edgeIds);
}

function applyGraphHighlight(nodeIds, edgeIds) {
  const nodeSet = new Set(nodeIds);
  const edgeSet = new Set(edgeIds);

  const nodeUpdates = [];
  graphNodes.forEach((node) => {
    const isHighlighted = nodeSet.has(node.id);
    const defaults = graphNodeDefaults[node.id] || {};
    nodeUpdates.push({
      id: node.id,
      size: isHighlighted ? NODE_HIGHLIGHT_SIZE : NODE_DEFAULT_SIZE,
      borderWidth: 0,
      shadow: false,
      font: isHighlighted ? buildHighlightFont(defaults.font) : defaults.font
    });
  });
  graphNodes.update(nodeUpdates);

  const edgeUpdates = [];
  graphEdges.forEach((edge) => {
    edgeUpdates.push({
      id: edge.id,
      width: edgeSet.has(edge.id) ? EDGE_HIGHLIGHT_WIDTH : EDGE_DEFAULT_WIDTH
    });
  });
  graphEdges.update(edgeUpdates);
}

function clearGraphHighlight() {
  const nodeUpdates = [];
  graphNodes.forEach((node) => {
    const defaults = graphNodeDefaults[node.id] || {};
    nodeUpdates.push({
      id: node.id,
      size: NODE_DEFAULT_SIZE,
      borderWidth: 0,
      shadow: false,
      font: defaults.font
    });
  });
  graphNodes.update(nodeUpdates);

  const edgeUpdates = [];
  graphEdges.forEach((edge) => {
    edgeUpdates.push({
      id: edge.id,
      width: EDGE_DEFAULT_WIDTH
    });
  });
  graphEdges.update(edgeUpdates);
}

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
        },
      selectionWidth: 3
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

  var preparedNodes = data.nodes.map((node) => ({
    ...node,
    size: NODE_DEFAULT_SIZE
  }));
  graphNodeDefaults = {};
  preparedNodes.forEach((node) => {
    graphNodeDefaults[node.id] = {
      font: node.font
    };
  });
  graphNodes = new vis.DataSet(preparedNodes);
  graphEdges = new vis.DataSet(data.edges);

  network = new vis.Network(container, {
    nodes: graphNodes,
    edges: graphEdges
  }, options);

  network.on("stabilizationIterationsDone", function () {
        network.setOptions( { physics: false } );
    });

  network.on("click", function (params) {
    if (params.nodes.length > 0) {
      selectLinkedNodes(params.nodes[0]);
      return;
    }

    if (params.edges.length > 0) {
      selectEdgeEndpoints(params.edges);
      return;
    }

    clearGraphHighlight();
  });

}


/* Page is ready, fetch the assets of the case */
$(document).ready(function(){
    get_case_graph();
});
