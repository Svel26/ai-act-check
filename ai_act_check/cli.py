import os
import json
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

import getpass

API_URL = os.getenv("ANNEXFOUR_API_URL", "https://annexfour.eu/api")

def load_env():
    env_path = Path('.') / '.env'
    if load_dotenv and env_path.exists():
        load_dotenv(dotenv_path=env_path)

def get_config_path():
    """Returns the path to the config file: ~/.config/ai-act-check/config.json"""
    config_dir = Path.home() / ".config" / "ai-act-check"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"

def load_config():
    """Loads configuration from JSON file."""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(new_config):
    """Updates configuration file with new values."""
    config = load_config()
    config.update(new_config)
    with open(get_config_path(), 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

def main():
    load_env()
    parser = argparse.ArgumentParser(prog='ai-act-check', description='AI Act static scanner and drafter')
    sub = parser.add_subparsers(dest='cmd', required=True)

    # LOGIN COMMAND
    p_login = sub.add_parser('login', help='Authenticate with Annexfour Platform')

    # SCAN COMMAND
    p_scan = sub.add_parser('scan', help='Run static AST scanner on a repository')
    p_scan.add_argument('path', nargs='?', help='Path to repository to scan (optional if --libs is used)')
    p_scan.add_argument('--libs', help='Comma-separated list of libraries to scan manually (e.g. "tensorflow,cv2")')
    p_scan.add_argument('--output', help='Path to save JSON output file')
    p_scan.add_argument('--token', help='API Token for Annexfour Platform (overrides config)')
    p_scan.add_argument('--project-name', help='Project Name for Annexfour Platform tracking')

    p_manual = sub.add_parser('manual', help='Interactive manual entry of libraries')

    p_draft = sub.add_parser('draft', help='Generate Annex IV draft from scan output')
    p_draft.add_argument('scan_json', nargs='?', help='Path to scan JSON file (optional)')

    args = parser.parse_args()

    if args.cmd == 'login':
        run_login()
    elif args.cmd == 'scan':
        # Token Resolution Priority:
        # 1. CLI Argument
        # 2. Environment Variable
        # 3. Config File
        token = args.token or os.getenv("ANNEXFOUR_API_TOKEN") or load_config().get("token")
        
        if not token and args.project_name:
             print("[!] Warning: --project-name provided but no API Token found.")
             print("    Run 'ai-act-check login' or provide --token to enable secure scanning.")

        run_scan(args.path, args.libs, args.output, token, args.project_name)
    elif args.cmd == 'manual':
        run_manual()
    elif args.cmd == 'draft':
        run_draft(args.scan_json)

def run_login():
    print("--- Annexfour Local Authentication ---")
    print("Please paste your API Token (generated in Settings -> Developer).")
    print("Input is hidden for security.")
    
    try:
        token = getpass.getpass("API Token: ").strip()
    except Exception:
        token = input("API Token: ").strip()

    if not token.startswith("anx_"):
        print("Error: Invalid token format. Token should start with 'anx_'.")
        return

    # Optional: We could verify the token against the API here, but for now we trust the format.
    save_config({"token": token})
    print(f"\n[+] Success! Token saved to {get_config_path()}")
    print("You can now run 'ai-act-check scan' without the --token argument.")

def initiate_remote_scan(data_dict, project_name, token):
    if not requests:
        print("Error: 'requests' library not installed. Please run 'pip install requests'")
        return None

    # Canonical Serialization for Hashing
    json_str = json.dumps(data_dict, sort_keys=True)
    content_hash = hashlib.sha256(json_str.encode("utf-8")).hexdigest()
    timestamp = datetime.utcnow().isoformat()

    payload = {
        "hash": content_hash,
        "project_name": project_name,
        "timestamp": timestamp
    }
    
    headers = {
        # "Authorization": f"Bearer {token}", # TODO: Implement Auth check if needed
        "Content-Type": "application/json"
    }

    try:
        # Assuming localhost for dev, should be strictly configured in prod
        url = f"{API_URL}/scans/initiate"
        print(f"[*] Contacting Annexfour Backend: {url}")
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            return resp.json().get("scan_id")
        else:
            print(f"Error initiating scan: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

def run_scan(repo_path, libs=None, output_path=None, token=None, project_name=None):
    try:
        # Lazy import to keep CLI fast if missing deps
        from ai_act_check.scanner import scan_repository, scan_libraries
    except Exception as e:
        print(f"Error: scanner module not available. {e}")
        return

    result = {}
    if libs:
        lib_list = [l.strip() for l in libs.split(',')]
        result = scan_libraries(lib_list)
    elif repo_path:
        result = scan_repository(repo_path)
    else:
        print("Error: You must provide either a repository path or --libs argument.")
        return

    # Secure Local Scan Flow
    if token:
        if not project_name:
            print("Error: --project-name is required when using --token")
            return
            
        print("[*] Secure Local Scan enabled. Calculating hash...")
        scan_id = initiate_remote_scan(result, project_name, token)
        
        if scan_id:
            print(f"[+] Remote Scan Initiated. ID: {scan_id}")
            result["scan_id"] = scan_id
        else:
            print("[!] Failed to initiate remote scan. Saving local report without ID.")

    out = json.dumps(result, indent=2)
    
    if output_path:
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(out)
            print(f"[+] Scan results saved to {output_path}")
        except Exception as e:
            print(f"Error saving output to {output_path}: {e}")
    else:
        print(out)

    print("\n[!] 3 High Risk libraries detected.")
    print("[+] Want to generate the official Annex IV PDF for this repo?")
    print("[+] Sign up at: https://annexfour.eu")

def run_manual():
    try:
        from ai_act_check.scanner import scan_libraries
    except Exception:
        print("Error: scanner module not available.")
        return

    print("--- AI Act Compliance: Manual Mode ---")
    print("Enter your AI/ML libraries separated by commas (e.g., tensorflow, face-api.js, torch).")
    user_input = input("Libraries: ")
    
    if not user_input.strip():
        print("No libraries entered. Exiting.")
        return

    lib_list = [l.strip() for l in user_input.split(',')]
    result = scan_libraries(lib_list)
    
    print("\n--- COMPLIANCE SCAN COMPLETE ---")
    print(json.dumps(result, indent=2))
    
    print("\nTo generate a draft, save the above JSON to a file (e.g., scan.json) and run:")
    print("  ai-act-check draft scan.json")

def run_draft(scan_json_path):
    # Load scan data from file
    if scan_json_path:
        try:
            with open(scan_json_path, 'r', encoding='utf-8') as f:
                scan_data = json.load(f)
        except Exception as e:
            print(f"Error reading scan JSON: {e}")
            return
    else:
        print("No scan JSON provided. Please run 'ai-act-check scan <path>' first or provide a scan JSON file.")
        return

    try:
        from ai_act_check.public_drafter import generate_teaser
    except Exception:
        print("Error: drafter module not available. Ensure package is installed or run from repo.")
        return

    print(f"[*] Generating Teaser Draft...")
    try:
        report = generate_teaser(scan_data)
    except Exception as e:
        print(f"Error during draft generation: {e}")
        return

    if not report:
        print("Draft generation failed or returned empty result.")
        return

    print("\n--- GENERATED ANNEX IV DRAFT (TEASER) ---\n")
    print(report)

    try:
        with open('ANNEX_IV_DRAFT.md', 'w', encoding='utf-8') as f:
            f.write(report)
        print("\n[+] Saved to ANNEX_IV_DRAFT.md")
        print("[!] This is a preliminary draft. For a full legal analysis and certified PDF, visit:")
        print("    https://sovereign-code.eu")
    except Exception as e:
        print(f"Error saving draft: {e}")

if __name__ == '__main__':
    main()