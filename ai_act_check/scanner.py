import ast
import os
import json
from typing import Dict, Any

# Scanner for AI Act detection.
# Loads RISK_LIBRARY_MAP from ai_act_check/risk_map.json if present,
# otherwise falls back to an embedded default.

DEFAULT_RISK_LIBRARY_MAP = {
    "face_recognition": "High Risk: Biometrics (Annex III.1)",
    "dlib": "High Risk: Biometrics (Annex III.1)",
    "opencv-python": "Potential Risk: Visual Analysis",
    "cv2": "Potential Risk: Visual Analysis",
    "sklearn": "General ML (Check for Employment/Credit Scoring)",
    "torch": "Deep Learning (Check for Generative/Biometric)",
    "pypdf2": "Potential Risk: Resume Parsing (Employment - Annex III.4)",
}

def load_risk_map() -> Dict[str, str]:
    """
    Try to load ai_act_check/risk_map.json from package. If not found,
    return the DEFAULT_RISK_LIBRARY_MAP.
    """
    pkg_map_path = os.path.join(os.path.dirname(__file__), "risk_map.json")
    if os.path.exists(pkg_map_path):
        try:
            with open(pkg_map_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # Fall back silently to default
            pass
    return DEFAULT_RISK_LIBRARY_MAP

class ComplianceScanner(ast.NodeVisitor):
    def __init__(self, risk_map: Dict[str, str]):
        self.detected_libraries = set()
        self.risk_flags = set()
        self.risk_map = risk_map

    def visit_Import(self, node):
        for alias in node.names:
            self._check_risk(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self._check_risk(node.module)
        self.generic_visit(node)

    def _check_risk(self, lib_name: str):
        # Naive check: does the library start with a known risk key?
        for risk_lib, risk_desc in self.risk_map.items():
            if lib_name.startswith(risk_lib):
                self.detected_libraries.add(lib_name)
                self.risk_flags.add(risk_desc)

def scan_repository(repo_path: str) -> Dict[str, Any]:
    """
    Walk the repository at repo_path and return a structure compatible
    with the annex_iv_schema for section_2_b_design_specifications.
    """
    risk_map = load_risk_map()
    scanner = ComplianceScanner(risk_map)

    print(f"[*] Scanning repository: {repo_path}...")

    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        source = f.read()
                        # Skip very large files to avoid memory spikes (optional)
                        if len(source) > 5_000_000:
                            # skip extremely large generated files
                            continue
                        tree = ast.parse(source)
                        scanner.visit(tree)
                except SyntaxError as e:
                    print(f"[!] Could not parse {file}: {e}")
                except Exception as e:
                    print(f"[!] Error reading/parsing {file}: {e}")

    return {
        "section_2_b_design_specifications": {
            "detected_libraries": sorted(list(scanner.detected_libraries)),
            "risk_classification_detected": sorted(list(scanner.risk_flags))
        }
    }

# Allow running as a lightweight script for local debugging
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m ai_act_check.scanner <path_to_repo>")
        sys.exit(1)
    repo_path = sys.argv[1]
    results = scan_repository(repo_path)
    print("\n--- COMPLIANCE SCAN COMPLETE ---")
    print(json.dumps(results, indent=2))