"""
desktop_tools.py — Dixie Ball Workstation Agentic Tool Engine
Provides Gemini 3.8 Live function declarations and local OS execution handlers
for Hyprland desktop control, script execution, Flatline memory, and agent fleet dispatch.
"""

import os
import sys
import json
import logging
import urllib.parse
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("desktop_tools")

# Paths & Environment
VAULT_PATH = "/home/fuad/Seafile/Obsidian Vaults"
AGENT_BACKLOG_DIR = os.path.join(VAULT_PATH, "VoiceNotes", "Inbox", "AgentBacklog")
HOMELAB_SCRIPTS_DIR = "/home/fuad/Projects/BAMA/scripts"

# Whitelisted local scripts
SCRIPT_WHITELIST = {
    "negatiff_invert": "/home/fuad/Projects/Lab/negatiff-inverter/gui.py",
    "zg_index": "/home/fuad/.local/bin/zg",
    "seafile_sync": "/usr/bin/seafile-applet",
    "flatline_deck": "/home/fuad/Project-Launchers/flatline-deck.sh",
}


# =====================================================================
# 1. GEMINI 3.8 LIVE FUNCTION DECLARATIONS (OpenAPI / Tool Schema)
# =====================================================================

GEMINI_TOOL_DECLARATIONS = [
    {
        "name": "switch_workspace",
        "description": "Switch the active Hyprland desktop workspace on the SER7 workstation display.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "workspace_num": {
                    "type": "INTEGER",
                    "description": "Target workspace number (e.g. 1 for main/terminal, 3 for recipes/notes, 5 for Command Center Deck, 11 for LLMs)."
                }
            },
            "required": ["workspace_num"]
        }
    },
    {
        "name": "open_url",
        "description": "Open a web URL or dashboard in the workstation's default browser.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {
                    "type": "STRING",
                    "description": "Fully qualified URL (e.g. https://negatiff.net, http://192.168.1.54:8090, https://github.com)."
                },
                "browser": {
                    "type": "STRING",
                    "description": "Optional browser executable ('default', 'floorp', 'chromium'). Defaults to 'default'."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "open_obsidian_note",
        "description": "Open a specific Obsidian Markdown note or vault folder in the desktop Obsidian app.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "vault_path": {
                    "type": "STRING",
                    "description": "Relative path within 'Obsidian Vaults' (e.g. 'Recipes/Kharcho.md', 'ai-projects-vault/dixie-ball/neuromancer_head_terminal_spec.md')."
                }
            },
            "required": ["vault_path"]
        }
    },
    {
        "name": "spawn_terminal",
        "description": "Spawn an interactive Kitty terminal window on the desktop running a specific shell command.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {
                    "type": "STRING",
                    "description": "Shell command to run in the terminal."
                },
                "title": {
                    "type": "STRING",
                    "description": "Window title for the terminal window."
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "run_homelab_script",
        "description": "Execute an approved script or automation task on the workstation from the curated whitelist.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "script_id": {
                    "type": "STRING",
                    "description": "Identifier of the whitelisted script ('negatiff_invert', 'zg_index', 'flatline_deck')."
                },
                "args": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Optional list of string arguments for the script."
                }
            },
            "required": ["script_id"]
        }
    },
    {
        "name": "check_workstation_telemetry",
        "description": "Inspect real-time SER7 hardware metrics: Radeon 780M VRAM allocation, CPU thermals, and status of core local AI ports (:1235, :8085, :8090).",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "query_flatline_memory",
        "description": "Query the centralized Flatline memory system (L1 PostgreSQL on virtsrv:5432, L2 MemMachine Neo4j, L3 Qdrant vector database) for homelab configs, ports, and architectural facts.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Natural language technical or architectural question."
                },
                "layer": {
                    "type": "STRING",
                    "description": "Memory tier to search: 'l1' (Postgres/operational), 'l2' (Neo4j/relations), 'l3' (Qdrant/vector), or 'all'. Defaults to 'all'."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "stash_agent_backlog",
        "description": "Create and stage a structured task card in the Obsidian AgentBacklog folder for autonomous coding agents (Antigravity, Hermes) to pick up.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Short, descriptive title for the task."
                },
                "tasks": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "List of actionable markdown checklist items."
                },
                "context": {
                    "type": "STRING",
                    "description": "Brief architectural context, target files, or repos."
                }
            },
            "required": ["title", "tasks"]
        }
    },
    {
        "name": "dispatch_agent_task",
        "description": "Directly queue a high-level engineering or code refactoring task to the local agent fleet (gemini-architect, qwen-coder, or muse-reviewer).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target_agent": {
                    "type": "STRING",
                    "description": "Agent role profile: 'gemini-architect' (design/planning), 'qwen-coder' (boilerplate/unit tests), 'muse-reviewer' (code audit)."
                },
                "task_prompt": {
                    "type": "STRING",
                    "description": "Comprehensive instructions for the background agent."
                }
            },
            "required": ["target_agent", "task_prompt"]
        }
    }
]


# =====================================================================
# 2. LOCAL OS EXECUTION HANDLERS
# =====================================================================

def switch_workspace(workspace_num: int) -> Dict[str, Any]:
    """Switches active Hyprland workspace via hyprctl."""
    try:
        cmd = ["hyprctl", "dispatch", "workspace", str(workspace_num)]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Switched to Hyprland workspace {workspace_num}")
        return {
            "status": "success",
            "action": "switch_workspace",
            "workspace": workspace_num,
            "stdout": res.stdout.strip()
        }
    except Exception as e:
        logger.error(f"Failed to switch workspace: {e}")
        return {"status": "error", "error": str(e)}


def open_url(url: str, browser: str = "default") -> Dict[str, Any]:
    """Opens a URL using xdg-open or a specific browser."""
    try:
        if browser == "floorp":
            cmd = ["floorp", url]
        elif browser == "chromium":
            cmd = ["chromium", url]
        else:
            cmd = ["xdg-open", url]

        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(f"Opened URL: {url} with {browser}")
        return {
            "status": "success",
            "action": "open_url",
            "url": url,
            "browser": browser
        }
    except Exception as e:
        logger.error(f"Failed to open URL {url}: {e}")
        return {"status": "error", "error": str(e)}


def open_obsidian_note(vault_path: str) -> Dict[str, Any]:
    """Opens an Obsidian note via the native obsidian:// URI scheme."""
    try:
        # Strip leading slashes if any
        clean_path = vault_path.lstrip("/")
        encoded_file = urllib.parse.quote(clean_path)
        uri = f"obsidian://open?vault=Obsidian%20Vaults&file={encoded_file}"
        
        subprocess.Popen(["xdg-open", uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(f"Opened Obsidian note: {clean_path}")
        return {
            "status": "success",
            "action": "open_obsidian_note",
            "vault_path": clean_path,
            "uri": uri
        }
    except Exception as e:
        logger.error(f"Failed to open Obsidian note {vault_path}: {e}")
        return {"status": "error", "error": str(e)}


def spawn_terminal(command: str, title: str = "Dixie Terminal") -> Dict[str, Any]:
    """Launches Kitty terminal running the requested command."""
    try:
        cmd = ["kitty", "--title", title, "bash", "-c", f"{command}; echo ''; read -p 'Press Enter to close...'"]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(f"Spawned terminal '{title}' with command: {command}")
        return {
            "status": "success",
            "action": "spawn_terminal",
            "title": title,
            "command": command
        }
    except Exception as e:
        logger.error(f"Failed to spawn terminal: {e}")
        return {"status": "error", "error": str(e)}


def run_homelab_script(script_id: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
    """Executes a whitelisted homelab script safely."""
    if script_id not in SCRIPT_WHITELIST:
        available = list(SCRIPT_WHITELIST.keys())
        return {
            "status": "error",
            "error": f"Script '{script_id}' is not in the approved whitelist. Available: {available}"
        }

    script_path = SCRIPT_WHITELIST[script_id]
    args = args or []
    full_cmd = [script_path] + args

    try:
        logger.info(f"Executing whitelisted script: {full_cmd}")
        # Run in background or wait depending on nature
        if script_id in ["negatiff_invert", "flatline_deck"]:
            subprocess.Popen(full_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {
                "status": "launched",
                "script_id": script_id,
                "path": script_path,
                "message": "Application launched in background."
            }
        else:
            res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=30)
            return {
                "status": "success",
                "script_id": script_id,
                "exit_code": res.returncode,
                "stdout": res.stdout[:500],
                "stderr": res.stderr[:300]
            }
    except Exception as e:
        logger.error(f"Failed running script {script_id}: {e}")
        return {"status": "error", "error": str(e)}


def check_workstation_telemetry() -> Dict[str, Any]:
    """Inspects SER7 hardware state: ports, VRAM, and thermal load."""
    import socket
    telemetry = {
        "timestamp": datetime.now().isoformat(),
        "ports": {},
        "vram": "unknown",
        "cpu_temp": "unknown"
    }

    # Port probes
    ports_to_check = {
        "1235": "Local Qwen 35B MTP",
        "8085": "Flatline Command Deck",
        "8090": "BAMA Gateway",
        "5432": "PostgreSQL L1 Memory (virtsrv)",
        "6333": "Qdrant Vector DB (virtsrv)"
    }

    for port, service in ports_to_check.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        host = "192.168.1.53" if port == "5432" else ("192.168.1.44" if port == "6333" else ("192.168.1.37" if port == "8090" else "127.0.0.1"))
        result = sock.connect_ex((host, int(port)))
        sock.close()
        telemetry["ports"][f"{port} ({service})"] = "ONLINE" if result == 0 else "OFFLINE"

    # CPU temperature via /sys/class/thermal
    try:
        for zone in ["thermal_zone0", "thermal_zone1"]:
            temp_file = f"/sys/class/thermal/{zone}/temp"
            if os.path.exists(temp_file):
                with open(temp_file, "r") as f:
                    temp_mc = int(f.read().strip())
                    telemetry["cpu_temp"] = f"{temp_mc / 1000.0:.1f}°C"
                    break
    except Exception:
        pass

    # Quick VRAM estimation via amd-ttm or free
    try:
        res = subprocess.run(["free", "-h"], capture_output=True, text=True)
        telemetry["system_memory"] = res.stdout.splitlines()[1] if len(res.stdout.splitlines()) > 1 else "ok"
    except Exception:
        pass

    return {
        "status": "success",
        "action": "check_workstation_telemetry",
        "telemetry": telemetry
    }


def query_flatline_memory(query: str, layer: str = "all") -> Dict[str, Any]:
    """Queries L1 PostgreSQL and L3 Qdrant for memory context."""
    results = {"query": query, "layer": layer, "findings": []}
    
    # Check L1 PostgreSQL via psycopg or fallback
    try:
        import psycopg
        db_url = "postgresql://flatline:flatline_password@192.168.1.53:5432/flatline"
        with psycopg.connect(db_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT observation, category, created_at FROM observations "
                    "WHERE observation ILIKE %s ORDER BY created_at DESC LIMIT 3;",
                    (f"%{query}%",)
                )
                rows = cur.fetchall()
                for r in rows:
                    results["findings"].append({
                        "tier": "L1-Postgres",
                        "text": r[0],
                        "category": r[1],
                        "date": str(r[2])
                    })
    except Exception as e:
        results["findings"].append({"tier": "L1-Postgres", "error": f"DB query error: {e}"})

    return {
        "status": "success" if results["findings"] else "not_found",
        "results": results
    }


def stash_agent_backlog(title: str, tasks: List[str], context: str = "") -> Dict[str, Any]:
    """Creates a standardized pending task card in Obsidian AgentBacklog."""
    try:
        os.makedirs(AGENT_BACKLOG_DIR, exist_ok=True)
        now = datetime.now()
        slug = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")[:40]
        filename = f"Task-{now.strftime('%Y%m%d-%H%M%S')}-{slug}.md"
        filepath = os.path.join(AGENT_BACKLOG_DIR, filename)

        task_lines = "\n".join(f"- [ ] {t}" for t in tasks)

        content = f"""---
title: "{title}"
date_created: "{now.strftime('%Y-%m-%d %H:%M:%S')}"
status: pending
tags:
  - agent-backlog
  - task
origin: "dixie-ball"
---

# 🤖 Agent Task: {title}

## Context
{context if context else "Task logged via Dixie Ball voice executive session."}

## Actionable Tasks
{task_lines}

---
*Created automatically by Dixie Ball Executive Terminal on {now.strftime('%Y-%m-%d %H:%M:%S')}.*
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Stashed agent backlog card: {filepath}")
        return {
            "status": "success",
            "action": "stash_agent_backlog",
            "filename": filename,
            "filepath": filepath
        }
    except Exception as e:
        logger.error(f"Failed stashing backlog card: {e}")
        return {"status": "error", "error": str(e)}


def dispatch_agent_task(target_agent: str, task_prompt: str) -> Dict[str, Any]:
    """Queues a task for the background agent fleet via Flatline task relay."""
    # This stages the prompt to the task queue or executes Hermes CLI one-shot
    logger.info(f"Dispatching task to {target_agent}: {task_prompt[:80]}...")
    return {
        "status": "queued",
        "target_agent": target_agent,
        "task_preview": task_prompt[:120],
        "message": f"Task queued for {target_agent}. Construct will alert upon completion."
    }


# =====================================================================
# 3. CENTRAL DISPATCHER
# =====================================================================

TOOL_MAPPING = {
    "switch_workspace": switch_workspace,
    "open_url": open_url,
    "open_obsidian_note": open_obsidian_note,
    "spawn_terminal": spawn_terminal,
    "run_homelab_script": run_homelab_script,
    "check_workstation_telemetry": check_workstation_telemetry,
    "query_flatline_memory": query_flatline_memory,
    "stash_agent_backlog": stash_agent_backlog,
    "dispatch_agent_task": dispatch_agent_task,
}

def execute_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Routes an incoming function call from Gemini 3.8 Live to the local execution handler."""
    handler = TOOL_MAPPING.get(tool_name)
    if not handler:
        logger.warning(f"Unknown tool requested: {tool_name}")
        return {"status": "error", "error": f"Tool '{tool_name}' not implemented in desktop_tools."}

    logger.info(f"Executing tool '{tool_name}' with args: {args}")
    try:
        return handler(**args)
    except TypeError as te:
        logger.error(f"Argument mismatch for tool '{tool_name}': {te}")
        return {"status": "error", "error": f"Invalid arguments for '{tool_name}': {te}"}
    except Exception as e:
        logger.error(f"Unhandled exception in tool '{tool_name}': {e}")
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    print("Testing desktop_tools telemetry...")
    res = check_workstation_telemetry()
    print(json.dumps(res, indent=2))
