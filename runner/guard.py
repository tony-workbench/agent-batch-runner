"""Pre-tool-use guard: path allow-lists, secret files, a few dangerous commands, no external connectors.

The guard reads the command text, so a path built inside a script is not seen. Treat it as a seatbelt, not a sandbox.
"""
import os
import re
import shlex
from pathlib import Path

SECRET_NAME = re.compile(r"(^|/)(\.env[^/]*|[^/]*credentials[^/]*|id_rsa[^/]*|id_ed25519[^/]*|[^/]*\.pem|[^/]*\.p12|[^/]*\.keychain[^/]*)$", re.I)
BASH_DENY = [
    (r"(^|[\s;&|(])sudo\b", "sudo is not allowed"),
    (r"\bsecurity\s+(find|add|delete|dump|import|export)", "the keychain is off limits"),
    (r"\blaunchctl\b|\bdefaults\s+write\b|\bscutil\b|\bpmset\b|\bnetworksetup\b", "system settings are off limits"),
    (r"\bkillall\b|\bpkill\b", "bulk process killing is not allowed"),
    (r"(^|[\s;&|])rm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)+(/|~|\$HOME)(/?\s|/?$)", "recursive delete of a top-level directory is not allowed"),
]
WRITE_COMMANDS = {"cp", "mv", "ln", "touch", "mkdir", "rm", "rmdir", "rsync", "install", "tee", "truncate", "chmod", "chown", "unlink"}
REDIRECT = re.compile(r"(?:^|[^<>0-9&])>>?\s*([^\s;&|<>]+)")


def _norm(path):
    return os.path.realpath(os.path.expanduser(str(path)))


def under(path, roots):
    p = _norm(path)
    return any(p == _norm(r) or p.startswith(_norm(r).rstrip("/") + "/") for r in roots)


def _strip_heredocs(cmd):
    return re.sub(r"<<-?\s*['\"]?(\w+)['\"]?.*?\n\1\b", "", cmd, flags=re.S)


def _bash_paths(cmd):
    """Return (read_paths, write_paths) found in the command text. Only absolute and ~ paths matter."""
    reads, writes = [], []
    for seg in re.split(r"[;&|\n]+", cmd):
        try:
            toks = shlex.split(seg)
        except ValueError:
            toks = seg.split()
        if not toks:
            continue
        paths = [t for t in toks[1:] if t.startswith(("/", "~"))]
        (writes if os.path.basename(toks[0]) in WRITE_COMMANDS else reads).extend(paths)
    writes.extend(REDIRECT.findall(cmd))
    return reads, writes


def check(tool_name, tool_input, read_roots, write_roots):
    """Return a refusal reason, or None when the call is allowed."""
    ti = tool_input or {}
    if tool_name.startswith("mcp__"):
        return "external connectors are not allowed"
    if tool_name in ("Write", "Edit", "NotebookEdit"):
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        if not under(path, write_roots):
            return f"writing outside the allowed folders: {path}"
    if tool_name in ("Read", "Glob", "Grep"):
        path = ti.get("file_path") or ti.get("path") or ""
        if path and (not under(path, read_roots) or SECRET_NAME.search(_norm(path))):
            return f"reading outside the allowed folders, or a secret file: {path}"
    if tool_name == "Bash":
        cmd = _strip_heredocs(ti.get("command") or "")
        for rx, why in BASH_DENY:
            if re.search(rx, cmd):
                return why
        reads, writes = _bash_paths(cmd)
        for t in writes:
            if t.startswith(("/", "~")) and not t.startswith("/dev/") and not under(t, write_roots):
                return f"command writes outside the allowed folders: {t}"
        for t in reads + writes:
            if not t.startswith(("/", "~")) or t.startswith("/dev/"):
                continue
            n = _norm(t)
            if SECRET_NAME.search(n) and os.path.exists(n):
                return f"{t} is a secret file"
            if os.path.exists(n) and not under(t, read_roots):
                return f"command reads outside the allowed folders: {t}"
    return None
