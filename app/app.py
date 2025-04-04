import os
import sys
from pathlib import Path
import dash
from dash import html, dcc, Input, Output, State
import dash_cytoscape as cy
import json

# Ensure local helpers (graph_builder*) are importable when executed via serverless import
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from graph_builder import (
    load_data,
    build_inheritance_graph,
    build_class_dependency_graph,
    build_call_graph,
)
from graph_builder_cy import nx_to_cytoscape, extract_neighbors_subgraph


DEFAULT_DATA_FILE = os.environ.get("DATA_FILE", "assets/fastapi_analysis_results.json")

data, G_default, elements_full = {}, None, []  # avoid unused variable warning

app = dash.Dash(__name__)
server = app.server

# -------------------------------------------
# Layout with sidebar
# -------------------------------------------
def create_layout(initial_elements):
    return html.Div([
    # ---------- Sidebar ----------
    html.Div([
        html.H3("⚙️ Control Panel", style={"textAlign": "center"}),
        
        html.Label("Graph Type"),
        dcc.Dropdown(
            id="graph-type",
            options=[
                {"label": "Inheritance", "value": "inherit"},
                {"label": "Call Graph", "value": "call"},
                {"label": "Class Dependency", "value": "dep"},
                {"label": "Class Method Calls", "value": "class_method_call"},  
            ],
            value="inherit",
            clearable=False
        ),

        html.Br(),

        html.Label("Search Class Name"),
        dcc.Input(
            id="search",
            type="text",
            placeholder="e.g. APIRoute",
            style={"width": "100%"}
        ),

        html.Br(), html.Br(),

        dcc.Checklist(
            id="expand-check",
            options=[{"label": "Expand Neighbor Subgraph", "value": "on"}],
            value=["on"]
        ),

        html.Label("Number of Hops to Expand"),
        dcc.Slider(
            id="hop-slider",
            min=1, max=4, step=1, value=2,
            marks={i: str(i) for i in range(1,5)}
        ),

        html.Br(),

        html.Label("Layout Type"),
        dcc.Dropdown(
            id="layout-type",
            options=[
                {"label": "cose", "value": "cose"},
                {"label": "breadthfirst", "value": "breadthfirst"},
                {"label": "circle", "value": "circle"},
                {"label": "grid", "value": "grid"},
                {"label": "random", "value": "random"},
            ],
            value="cose",
            clearable=False
        ),

        html.Br(),

        html.Button("Reset Graph", id="reset-btn", n_clicks=0, style={"width": "100%"}),

    ], style={
        "position": "fixed",
        "left": 0,
        "top": 0,
        "bottom": 0,
        "width": "260px",
        "padding": "20px",
        "background": "#F5F5F5",
        "overflowY": "auto",
        "border-right": "1px solid #DDD"
    }),

    # ---------- Main content ----------
    html.Div([
        cy.Cytoscape(
            id='cytoscape-graph',
            elements=initial_elements,
            style={'width': '100%', 'height': '750px'},
            layout={'name': 'cose'},
            stylesheet=[
                {
                    "selector": "node",
                    "style": {
                        "label": "data(label)",
                        "background-color": "#4C90FF",
                        "color": "Black",
                        "width": 40,
                        "height": 40,
                        "font-size": "10px"
                    }
                },
                {
                    "selector": ".edge",
                    "style": {
                        "curve-style": "bezier",
                        "width": 2,
                        "line-color": "#AAAAAA",
                    }
                },
                {
                    "selector": ".directed",
                    "style": {
                        "target-arrow-shape": "triangle",
                        "arrow-scale": 1.5,
                        "curve-style": "bezier"
                    }
                },
                {
                    "selector": ":selected",
                    "style": {
                        "background-color": "#FF5733",
                        "width": 55,
                        "height": 55
                    }
                }
            ]

        ),

        html.Div(id="info", style={"marginTop": "20px"})
    ],
        style={"marginLeft": "280px", "padding": "20px"}
    )
    ])


app.layout = create_layout(elements_full)

def bootstrap_data(data_path: str):
    """Load graph data either from env var or CLI argument for serverless imports."""
    global data, G_default, elements_full
    if not data_path:
        return

    try:
        data = load_data(data_path)
    except FileNotFoundError:
        print(f"[bootstrap] Data file '{data_path}' not found. App will start empty.")
        return
    except json.JSONDecodeError as exc:
        print(f"[bootstrap] Failed to parse '{data_path}': {exc}")
        return

    G_default = build_inheritance_graph(data)
    elements_full = nx_to_cytoscape(G_default)
    app.layout = create_layout(elements_full)


# Load default data immediately so serverless imports have content
bootstrap_data(DEFAULT_DATA_FILE)

# -------------------------------------------
# Callbacks
# -------------------------------------------
@app.callback(
    Output("cytoscape-graph", "elements"),
    Output("info", "children"),
    Output("cytoscape-graph", "layout"),
    Input("cytoscape-graph", "tapNodeData"),
    Input("graph-type", "value"),
    Input("search", "value"),
    Input("expand-check", "value"),
    Input("hop-slider", "value"),
    Input("layout-type", "value"),
    Input("reset-btn", "n_clicks"),
)
def update_graph(nodeData, graph_type, search, expand_check, hops, layout_type, reset):
    triggered = dash.callback_context.triggered[0]['prop_id']
    layout_config = {"name": layout_type or "cose"}

    # Build graph according to selection
    is_directed = False
    if graph_type == "inherit":
        G = build_inheritance_graph(data)
        is_directed = True
    elif graph_type == "call":
        G = build_call_graph(data)
        is_directed = True
    elif graph_type == "class_method_call":     
        from graph_builder import build_class_method_call_graph
        G = build_class_method_call_graph(data)
        is_directed = True
    else:
        G = build_class_dependency_graph(data)
        is_directed = True


    elements_full = nx_to_cytoscape(G, directed=is_directed)
    info_text = "Click a node to see class info"

    # Reset button
    if "reset-btn" in triggered:
        return elements_full, "Graph reset to full view", layout_config

    # Search
    if search and search in G.nodes:
        center = search
    elif nodeData:
        center = nodeData["id"]
    else:
        return elements_full, info_text, layout_config

    # If expand neighbors OFF → highlight only
    if "on" not in expand_check:
        info_text = f"Selected: {center}"
        return elements_full, info_text, layout_config

    # Expand neighbors
    subG = extract_neighbors_subgraph(G, center, hops=hops)
    sub_elements = nx_to_cytoscape(subG, directed=is_directed)

    # Build node info
    info = None
    for module, classes in data.items():
        if center in classes:
            info = json.dumps(classes[center], indent=2, ensure_ascii=False)
            break

    return sub_elements, info or f"Node: {center}", layout_config


if __name__ == '__main__':

    # support argument parsing
    import argparse

    parser = argparse.ArgumentParser(description="Dash App for Visualizing Class Graphs")
    # input file
    parser.add_argument("--data", type=str, default=DEFAULT_DATA_FILE, help="Path to analysis JSON file")
    args = parser.parse_args()

    if args.data:
        bootstrap_data(args.data)

    app.run(debug=True)
