import json
import re
import networkx as nx
from pyvis.network import Network


def load_data(path):
    return json.load(open(path, "r", encoding="utf8"))


def build_inheritance_graph(data):
    G = nx.DiGraph()
    for module, classes in data.items():
        for cls, info in classes.items():
            for base in info["bases"]:
                G.add_edge(base, cls)
    return G


def build_call_graph(data):
    """
    Build a simple call graph:
    node: "Class.method"
    edge: Class.method -> callee (string, e.g. "B.bb" or "APIRoute.get_route_handler")
    """
    import networkx as nx
    G = nx.DiGraph()

    for module, classes in data.items():
        for cls, info in classes.items():
            for m, m_info in info["methods"].items():
                src = f"{cls}.{m}"
                G.add_node(src)

                for call in m_info["calls"]:
                    if isinstance(call, dict):
                        callee = call.get("callee") or call.get("raw")
                    else:
                        callee = call

                    if not callee:
                        continue

                    G.add_node(callee)
                    G.add_edge(src, callee)

    return G




def build_class_dependency_graph(data):
    """
    Build a class dependency graph where an edge A -> B means
    \"Class A uses Class B\" somewhere in its definition.
    Usage is detected via:
      * inheriting from B
      * having an attribute typed as B
      * calling a method that references B or B.some_method
      * instantiating B() inside a method body
    """

    G = nx.DiGraph()
    instantiation_pattern = re.compile(r"([A-Z][A-Za-z0-9_]+)\(")

    # Collect available class names once so we can filter dependencies
    all_classes = {cls for classes in data.values() for cls in classes}

    def add_dependency(user: str, target: str):
        """Add a dependency edge user -> target if both are known classes."""
        if not target or user == target:
            return
        if target in all_classes:
            G.add_edge(user, target)

    for module, classes in data.items():
        for cls_name, info in classes.items():
            G.add_node(cls_name)

            # Inheritance: subclass uses its base classes
            for base in info.get("bases", []):
                add_dependency(cls_name, base)

            # Attributes typed as other classes
            for attr_type in info.get("attributes", {}).values():
                add_dependency(cls_name, attr_type)

            # Method-level usages coming from calls or explicit instantiations
            for m_info in info.get("methods", {}).values():
                for call in m_info.get("calls", []):
                    if isinstance(call, dict):
                        callee = call.get("callee") or call.get("raw")
                    else:
                        callee = call

                    if not isinstance(callee, str):
                        continue

                    callee_clean = callee.split("(")[0]
                    candidate = callee_clean.split(".")[-1]
                    add_dependency(cls_name, candidate)

                    for instantiated in instantiation_pattern.findall(callee):
                        add_dependency(cls_name, instantiated)

    return G



def build_class_method_call_graph(data):
    """
    Build graph where each node = Class.method
    Edge: Class.method  ->  OtherClass.otherMethod
    """

    import networkx as nx
    G = nx.DiGraph()

    for module, classes in data.items():
        for cls, info in classes.items():
            for method, m_info in info["methods"].items():
                caller = f"{cls}.{method}"
                G.add_node(caller)

                # each callee is a dict {'caller', 'callee', 'raw'}
                for call in m_info["calls"]:
                    callee = call.get("callee")
                    if not callee:
                        continue

                    # e.g. "B.bb"
                    callee_clean = callee.replace("self.", f"{cls}.")
                    G.add_node(callee_clean)
                    G.add_edge(caller, callee_clean)

    return G

def export_pyvis(G, output="graph.html"):
    net = Network(height="800px", width="100%", directed=True)
    net.from_nx(G)
    net.show(output, notebook=False)
