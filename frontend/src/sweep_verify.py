import os, subprocess, re, glob, sys
SITE = "test1-erp.batchprojects.com"
CLIENTS = "/home/frappe/batcherp/clients"
STATE_DIR = os.path.expanduser("~/.claude/tools/pw-state")

def resolve_port(site):
    hits = glob.glob(f"{CLIENTS}/*/sites/{site}")
    clients = [h.split("/")[-3] for h in hits]
    out = subprocess.run(["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"], capture_output=True, text=True, check=True).stdout
    ports_by_name = dict(line.partition("\t")[::2] for line in out.splitlines())
    for client in clients:
        m = re.search(r"127\.0\.0\.1:(\d+)->8000/tcp", ports_by_name.get(f"{client}-backend", ""))
        if m: return int(m.group(1))
    sys.exit("no port")

port = resolve_port(SITE)
base = f"http://{SITE}:{port}"
state_file = os.path.join(STATE_DIR, f"{SITE}.json")

from playwright.sync_api import sync_playwright
errors = {}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=[f"--host-resolver-rules=MAP {SITE} 127.0.0.1"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, storage_state=state_file)

    pages_to_check = [
        ("workspace", f"{base}/workspace"),
        ("teams", f"{base}/workspace/teams"),
        ("reports", f"{base}/workspace/reports"),
    ]
    for name, url in pages_to_check:
        page = ctx.new_page()
        console_errors = []
        page.on("console", lambda m, ce=console_errors: ce.append(m.text) if m.type == "error" else None)
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1200)
        page.screenshot(path=f"sweep_{name}.png")
        errors[name] = [e for e in console_errors if "session/bootstrap" not in e]
        page.close()

    browser.close()
print(errors)
