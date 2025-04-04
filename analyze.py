import ast
import os
from collections import defaultdict

class Analyzer(ast.NodeVisitor):
    def __init__(self, module):
        self.module = module
        self.classes = {}
        self.current_class = None
        self.current_method = None

    # -------------------------
    # CLASS
    # -------------------------
    def visit_ClassDef(self, node):
        bases = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except:
                pass
        
        self.current_class = node.name
        self.classes[node.name] = {
            "module": self.module,
            "bases": bases,
            "attributes": {},
            "methods": {},
        }

        self.generic_visit(node)
        self.current_class = None

    # -------------------------
    # METHOD
    # -------------------------
    def visit_FunctionDef(self, node):
        if self.current_class:
            self.current_method = node.name
            self.classes[self.current_class]["methods"][node.name] = {
                "calls": []
            }

            self.generic_visit(node)
            self.current_method = None

        else:
            # skip module-level fn
            pass

    # -------------------------
    # ATTRIBUTE
    # -------------------------
    def visit_Assign(self, node):
        if self.current_class:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.classes[self.current_class]["attributes"][target.id] = "Unknown"
        self.generic_visit(node)

    # -------------------------
    # CALL extraction
    # -------------------------
    def visit_Call(self, node):
        """
        Extract calls:
            B.bb()
            self.x.y()
            module.A.b()
            foo()
        """
        if self.current_class and self.current_method:

            callee = self.get_full_attr_name(node.func)
            fq_caller = f"{self.current_class}.{self.current_method}"

            if callee:
                normalized = self.normalize_callee(callee)
                self.classes[self.current_class]["methods"][self.current_method]["calls"].append({
                    "caller": fq_caller,
                    "callee": normalized,
                    "raw": callee
                })

        self.generic_visit(node)

    # -------------------------
    # Extract full dotted name
    # -------------------------
    def get_full_attr_name(self, node):
        """
        Convert:
            self.x.y.z → "self.x.y.z"
            A.b        → "A.b"
            module.A.b → "module.A.b"
            foo        → "foo"
        """

        # simple Name: foo()
        if isinstance(node, ast.Name):
            return node.id

        # dotted chain: module.A.b()
        if isinstance(node, ast.Attribute):
            parts = []
            curr = node
            while isinstance(curr, ast.Attribute):
                parts.append(curr.attr)
                curr = curr.value

            if isinstance(curr, ast.Name):  # root of chain
                parts.append(curr.id)
            else:
                # unsupported (e.g., Call)
                return None

            return ".".join(reversed(parts))

        return None

    # -------------------------
    # Normalize callee name
    # -------------------------
    def normalize_callee(self, callee):
        """
        Examples:
            self.b        → A.b
            self.x.y.z    → A.x.y.z
            B.bb          → B.bb
            module.A.b    → module.A.b
            foo           → foo   (module-level function)
        """
        if callee.startswith("self."):
            return callee.replace("self.", f"{self.current_class}.", 1)

        # If first part is Capitalized → class method
        first = callee.split(".")[0]
        if first[:1].isupper():
            return callee

        # module-level call
        return callee


def analyze_root(root_path):
    results = {}
    for root, _, files in os.walk(root_path):
        for f in files:
            if f.endswith(".py"):
                full = os.path.join(root, f)
                module = os.path.relpath(full, root_path).replace("/", ".")[:-3]

                try:
                    tree = ast.parse(open(full, "r", encoding="utf8").read())
                except Exception:
                    continue

                analyzer = Analyzer(module)
                analyzer.visit(tree)
                results[module] = analyzer.classes

    return results


if __name__ == "__main__":
    import json
    import argparse

    parser = argparse.ArgumentParser(description="Analyze Python project")
    parser.add_argument("path", nargs="?", help="Path to the root of the Python project")
    parser.add_argument("output", nargs="?", help="Output JSON file")
    args = parser.parse_args()

    # check path
    if not args.path or not os.path.isdir(args.path):
        print("Please provide a valid path to a Python project directory.")
        exit(1)

    res = analyze_root(args.path) 

    base_name = os.path.basename(args.path)
    print( f"Analyzed project: {base_name}" )
    file_name = args.output or base_name + "_analysis_results"
    file_name += ".json" if not file_name.endswith(".json") else ""
    file_path = os.path.join(os.path.dirname(os.path.abspath(args.path)), file_name)

    json.dump(res, open(file_path, "w", encoding="utf8"), indent=2)
    print(f"Done. Output: {file_path}")
