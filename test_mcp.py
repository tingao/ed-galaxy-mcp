#!/usr/bin/env python3
"""Proper MCP protocol test — sends init, then tools/list, then a tool call."""
import subprocess, json, sys

proc = subprocess.Popen(
    [sys.executable, "-m", "ed_galaxy_mcp.server"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
)

def send_req(req: dict) -> dict:
    line = json.dumps(req) + "\n"
    proc.stdin.write(line)
    proc.stdin.flush()
    resp = proc.stdout.readline()
    return json.loads(resp) if resp.strip() else {}

# 1. Initialize
init_resp = send_req({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0"},
    }
})
print("Initialize:", json.dumps(init_resp, indent=2)[:200])

# 2. Initialized notification (no response expected)
proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
proc.stdin.flush()

# 3. List tools
tools_resp = send_req({
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {},
})
if "result" in tools_resp:
    tools = tools_resp["result"].get("tools", [])
    print(f"\n=== {len(tools)} TOOLS ===")
    for t in tools:
        print(f"  [{t['name']}] {t.get('description', '')[:100]}")
else:
    print("Tools response:", json.dumps(tools_resp, indent=2)[:500])

# 4. Call get_system Sol
call_resp = send_req({
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
        "name": "get_system",
        "arguments": {"name_or_id64": "Sol"},
    },
})
if "result" in call_resp:
    content = call_resp["result"].get("content", [])
    for c in content:
        text = c.get("text", "")[:300]
        print(f"\n=== get_system('Sol') ===")
        print(text)
else:
    print("Call response:", json.dumps(call_resp, indent=2)[:500])

# 5. Search for Diaguandri
search_resp = send_req({
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
        "name": "search_systems",
        "arguments": {"query": "Diaguandri"},
    },
})
if "result" in search_resp:
    content = search_resp["result"].get("content", [])
    for c in content:
        text = c.get("text", "")[:300]
        print(f"\n=== search_systems('Diaguandri') ===")
        print(text)

proc.terminate()
proc.wait()
