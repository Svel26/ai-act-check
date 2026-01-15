import ast
import os
import json
import sys
import re
from typing import Dict, Set, Tuple, List, Any

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RISK_MAP_PATH = os.path.join(CURRENT_DIR, "data", "risk_map.json")

try:
    with open(RISK_MAP_PATH, "r", encoding="utf-8") as f:
        RISK_LIBRARY_MAP: Dict[str, str] = json.load(f)
except FileNotFoundError:
    print(f"[!] CRITICAL: Could not find risk_map.json at {RISK_MAP_PATH}")
    RISK_LIBRARY_MAP = {}
except Exception as e:
    print(f"[!] Error loading risk_map.json: {e}")
    RISK_LIBRARY_MAP = {}

def _parse_poetry_lock(file_path: str) -> Set[str]:
    libraries = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            in_package = False
            for line in f:
                line = line.strip()
                if line == "[[package]]":
                    in_package = True
                    continue
                
                if in_package and line.startswith("name ="):
                    parts = line.split("=")
                    if len(parts) == 2:
                        name = parts[1].strip().strip('"').strip("'")
                        libraries.add(name)
                    in_package = False
    except Exception:
        pass
    return libraries

def _parse_package_lock(file_path: str) -> Set[str]:
    libraries = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            deps = data.get("dependencies", {})
            for name in deps:
                libraries.add(name)
            packages = data.get("packages", {})
            for key in packages:
                if key.startswith("node_modules/"):
                    name = key.replace("node_modules/", "")
                    libraries.add(name)
    except Exception:
        pass
    return libraries

def _parse_requirements(file_path: str) -> Set[str]:
    libraries = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.match(r"^([a-zA-Z0-9_\-]+)", line)
                if match:
                    libraries.add(match.group(1))
    except Exception:
        pass
    return libraries

class CodeScanner(ast.NodeVisitor):
    """Scans Python source code (AST) for imports matching risk map."""
    def __init__(self) -> None:
        self.detected: Set[str] = set()
        self.risks: Set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self._check(node.module)
        self.generic_visit(node)

    def _check(self, name: str) -> None:
        for lib, risk in RISK_LIBRARY_MAP.items():
            if name.startswith(lib):
                self.detected.add(name)
                self.risks.add(risk)

def scan_dependency_files(repo_path: str) -> Tuple[Set[str], Set[str]]:
    detected: Set[str] = set()
    risks: Set[str] = set()

    target_files = {
        "requirements.txt", "package.json", "pyproject.toml", "Pipfile",
        "go.mod", "Cargo.toml", "pom.xml", "Gemfile", "composer.json", "build.gradle"
    }

    for root, _, files in os.walk(repo_path):
        for file in files:
            full_path = os.path.join(root, file)
            
            # Specialized Parsers
            if file == "poetry.lock":
                detected.update(_parse_poetry_lock(full_path))
                continue
            elif file == "package-lock.json":
                detected.update(_parse_package_lock(full_path))
                continue
            elif file == "requirements.txt":
                detected.update(_parse_requirements(full_path))
                continue
            
            # Fallback for other manifests
            if file in target_files:
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        for risk_lib, risk_desc in RISK_LIBRARY_MAP.items():
                            if risk_lib in content:
                                # heuristic to reduce false positives for manifests
                                # We look for the library name surrounded by quotes, whitespace, or common delimiters
                                pattern = rf'(?:^|[\s"\'/<>.-])({re.escape(risk_lib)})(?:$|[\s"\'/:>=<>.-])'
                                if re.search(pattern, content):
                                    detected.add(risk_lib)
                                    risks.add(risk_desc)
                except Exception:
                    continue

    # Map detected libs to risks
    for lib in detected:
        for risk_lib, risk_desc in RISK_LIBRARY_MAP.items():
            if lib == risk_lib or lib.startswith(risk_lib):
                risks.add(risk_desc)

    return detected, risks

def _convert_ipynb_to_py(file_path: str) -> str:
    """Converts a .ipynb file to a temporary .py file string content."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            nb = json.load(f)
        
        code_cells = []
        for cell in nb.get("cells", []):
            if cell.get("cell_type") == "code":
                # Filter out magic commands
                source_lines = [
                    line for line in cell["source"] 
                    if not line.strip().startswith(("!", "%"))
                ]
                code_cells.append("".join(source_lines))
        return "\n\n".join(code_cells)
    except Exception:
        return ""

def _extract_version(repo_path: str) -> str:
    """Attempts to extract project version from standard manifest files."""
    project_version = "Unknown"
    try:
        # Check package.json
        pkg_json_path = os.path.join(repo_path, "package.json")
        if os.path.exists(pkg_json_path):
            with open(pkg_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                project_version = data.get("version", "Unknown")
        
        # Check pyproject.toml
        if project_version == "Unknown":
            toml_path = os.path.join(repo_path, "pyproject.toml")
            if os.path.exists(toml_path):
                with open(toml_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("version"):
                            parts = line.split("=")
                            if len(parts) == 2:
                                project_version = parts[1].strip().strip('"').strip("'")
                                break
        
        # Check setup.py
        if project_version == "Unknown":
            setup_path = os.path.join(repo_path, "setup.py")
            if os.path.exists(setup_path):
                with open(setup_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    match = re.search(r"version\s*=\s*['\"]([^'\"]+)['\"]", content)
                    if match:
                        project_version = match.group(1)
    except Exception:
        pass
    return project_version

def scan_libraries(lib_list: List[str]) -> Dict[str, Any]:
    detected: Set[str] = set()
    risks: Set[str] = set()

    for lib in lib_list:
        lib = lib.strip()
        for risk_lib, risk_desc in RISK_LIBRARY_MAP.items():
            if lib == risk_lib or lib.startswith(risk_lib):
                detected.add(lib)
                risks.add(risk_desc)
    
    final_libs = sorted(list(detected))
    final_risks = sorted(list(risks))
    
    return _format_results(final_libs, final_risks)

def scan_repository(repo_path: str) -> Dict[str, Any]:
    ast_scanner = CodeScanner()
    
    # Extract version first
    project_version = _extract_version(repo_path)

    for root, _, files in os.walk(repo_path):
        for file in files:
            full_path = os.path.join(root, file)
            
            # Handle .py files
            if file.endswith(".py"):
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        source = f.read()
                        if len(source) > 5_000_000:
                            continue
                        tree = ast.parse(source)
                        ast_scanner.visit(tree)
                except Exception:
                    continue
            
            # Handle .ipynb files
            elif file.endswith(".ipynb"):
                try:
                    source = _convert_ipynb_to_py(full_path)
                    if source:
                        tree = ast.parse(source)
                        ast_scanner.visit(tree)
                except Exception:
                    continue

    dep_libs, dep_risks = scan_dependency_files(repo_path)

    final_libs = sorted(list(ast_scanner.detected.union(dep_libs)))
    final_risks = sorted(list(ast_scanner.risks.union(dep_risks)))

    results = _format_results(final_libs, final_risks)
    results["project_metadata"] = {"version": project_version}
    return results

def _format_results(detected_libs: List[str], detected_risks: List[str]) -> Dict[str, Any]:
    return {
        "annex_iv_technical_documentation": {
            "section_2_b_design_specifications": {
                "general_logic": {
                    "detected_libraries": detected_libs,
                    "risk_classification_detected": detected_risks,
                    "model_architecture": None
                },
                "key_design_choices": {
                    "framework": None,
                    "loss_functions": []
                }
            }
        }
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m ai_act_check.scanner <path_to_repo>")
        sys.exit(1)
    repo_path = sys.argv[1]
    results = scan_repository(repo_path)
    print("\n--- COMPLIANCE SCAN COMPLETE ---")
    print(json.dumps(results, indent=2))