"""Run one task in its own process with the Claude Agent SDK."""
import asyncio
import json
import sys
import time
from pathlib import Path

from . import guard, tasks
from .config import load
from .prompts import SUBAGENTS, SYSTEM_PROMPT, task_prompt

TOOLS = ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "WebSearch", "WebFetch", "Agent"]


def build_options(cfg, task, log_path):
    from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions, HookMatcher

    async def pre_tool_use(data, tool_use_id, context):
        why = guard.check(data.get("tool_name", ""), data.get("tool_input"), cfg.read_roots, cfg.write_roots)
        if why:
            with log_path.open("a") as f:
                f.write(f"{time.strftime('%H:%M:%S')} blocked {data.get('tool_name')}: {why}\n")
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": why}}
        return {}

    async def touch_progress(data, tool_use_id, context):
        log_path.with_suffix(".progress").touch()
        return {}

    subagents = {
        name: AgentDefinition(description=desc, prompt=SYSTEM_PROMPT + "\nYou are a subagent. " + desc, model="inherit",
                              tools=[t for t in TOOLS if t != "Agent" and not (name == "reviewer" and t == "Edit")])
        for name, desc in SUBAGENTS.items()
    }
    return ClaudeAgentOptions(
        cwd=str(cfg.root), model=cfg["model"],
        system_prompt={"type": "preset", "preset": "claude_code", "append": SYSTEM_PROMPT},
        agents=subagents, tools=TOOLS, allowed_tools=TOOLS, permission_mode="bypassPermissions",
        hooks={"PreToolUse": [HookMatcher(hooks=[pre_tool_use])], "PostToolUse": [HookMatcher(hooks=[touch_progress])]},
    )


async def run_task(cfg, task):
    from claude_agent_sdk import ResultMessage, query
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    log_path = cfg.state_dir / f"{task['id']}.log"
    cost = 0.0
    async for msg in query(prompt=task_prompt(cfg, task), options=build_options(cfg, task, log_path)):
        log_path.with_suffix(".progress").touch()
        if isinstance(msg, ResultMessage):
            cost = msg.total_cost_usd or 0.0
    with (cfg.state_dir / "usage.jsonl").open("a") as f:
        f.write(json.dumps({"id": task["id"], "estimated_cost_usd": cost, "t": time.time()}) + "\n")


def main(task_id, config_path=None):
    cfg = load(config_path)
    task = tasks.items(cfg.task_table)[task_id]
    asyncio.run(run_task(cfg, task))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
