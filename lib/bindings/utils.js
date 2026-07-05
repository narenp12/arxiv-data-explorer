const NODE_DIM_COLOR = "rgba(200,200,200,0.5)";
const NODE_SECONDARY_DIM_COLOR = "rgba(150,150,150,0.75)";

function buildUpdateArray(nodeMap) {
	return Object.keys(nodeMap).map((id) => nodeMap[id]);
}

function saveLabel(node) {
	if (node.hiddenLabel === undefined) {
		node.hiddenLabel = node.label;
		node.label = undefined;
	}
}

function restoreLabel(node) {
	if (node.hiddenLabel !== undefined) {
		node.label = node.hiddenLabel;
		node.hiddenLabel = undefined;
	}
}

function neighbourhoodHighlight(params) {
	allNodes = nodes.get({ returnType: "Object" });

	if (params.nodes.length > 0) {
		highlightActive = true;
		const selectedNode = params.nodes[0];
		const degrees = 2;

		for (const nodeId in allNodes) {
			allNodes[nodeId].color = NODE_DIM_COLOR;
			saveLabel(allNodes[nodeId]);
		}

		const connectedNodes = network.getConnectedNodes(selectedNode);
		let allConnectedNodes = [];

		for (let i = 1; i < degrees; i++) {
			for (let j = 0; j < connectedNodes.length; j++) {
				allConnectedNodes = allConnectedNodes.concat(
					network.getConnectedNodes(connectedNodes[j])
				);
			}
		}

		for (let i = 0; i < allConnectedNodes.length; i++) {
			allNodes[allConnectedNodes[i]].color = NODE_SECONDARY_DIM_COLOR;
			restoreLabel(allNodes[allConnectedNodes[i]]);
		}

		for (let i = 0; i < connectedNodes.length; i++) {
			allNodes[connectedNodes[i]].color = nodeColors[connectedNodes[i]];
			restoreLabel(allNodes[connectedNodes[i]]);
		}

		allNodes[selectedNode].color = nodeColors[selectedNode];
		restoreLabel(allNodes[selectedNode]);

		nodes.update(buildUpdateArray(allNodes));
	} else if (highlightActive === true) {
		for (const nodeId in allNodes) {
			allNodes[nodeId].color = nodeColors[nodeId];
			restoreLabel(allNodes[nodeId]);
		}
		highlightActive = false;
		nodes.update(buildUpdateArray(allNodes));
	}
}

function filterHighlight(params) {
	allNodes = nodes.get({ returnType: "Object" });

	if (params.nodes.length > 0) {
		filterActive = true;
		const selectedNodes = params.nodes;

		for (const nodeId in allNodes) {
			allNodes[nodeId].hidden = true;
			if (allNodes[nodeId].savedLabel === undefined) {
				allNodes[nodeId].savedLabel = allNodes[nodeId].label;
				allNodes[nodeId].label = undefined;
			}
		}

		for (let i = 0; i < selectedNodes.length; i++) {
			allNodes[selectedNodes[i]].hidden = false;
			if (allNodes[selectedNodes[i]].savedLabel !== undefined) {
				allNodes[selectedNodes[i]].label = allNodes[selectedNodes[i]].savedLabel;
				allNodes[selectedNodes[i]].savedLabel = undefined;
			}
		}

		nodes.update(buildUpdateArray(allNodes));
	} else if (filterActive === true) {
		for (const nodeId in allNodes) {
			allNodes[nodeId].hidden = false;
			if (allNodes[nodeId].savedLabel !== undefined) {
				allNodes[nodeId].label = allNodes[nodeId].savedLabel;
				allNodes[nodeId].savedLabel = undefined;
			}
		}
		filterActive = false;
		nodes.update(buildUpdateArray(allNodes));
	}
}

function selectNode(nodes) {
	network.selectNodes(nodes);
	neighbourhoodHighlight({ nodes: nodes });
	return nodes;
}

function selectNodes(nodes) {
	network.selectNodes(nodes);
	filterHighlight({ nodes: nodes });
	return nodes;
}

function highlightFilter(filter) {
	let selectedNodes = [];
	const selectedProp = filter["property"];
	if (filter["item"] === "node") {
		const allNodes = nodes.get({ returnType: "Object" });
		for (const nodeId in allNodes) {
			if (allNodes[nodeId][selectedProp] && filter["value"].includes((allNodes[nodeId][selectedProp]).toString())) {
				selectedNodes.push(nodeId);
			}
		}
	} else if (filter["item"] === "edge") {
		const allEdges = edges.get({ returnType: "object" });
		for (const edge in allEdges) {
			if (allEdges[edge][selectedProp] && filter["value"].includes((allEdges[edge][selectedProp]).toString())) {
				selectedNodes.push(allEdges[edge]["from"]);
				selectedNodes.push(allEdges[edge]["to"]);
			}
		}
	}
	selectNodes(selectedNodes);
}
