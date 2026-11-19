"""Load the runner configuration from a JSON file."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULTS = {
    "model": "claude-sonnet-5-5",
    "workers": 3,
    "base_seconds": 3600,
    "extend_seconds": 1800,
    "idle_seconds": 600,
    "max_seconds": 14400,
    "max_failures_per_task": 2,
    "throttle_after_bad_ends": 3,
    "heavy_pattern": "GPU|CUDA|Docker|training",
    "rules_docs": ["RULES.md", "STYLE_GUIDE.md", "REVIEW_CHECKLIST.md"],
    "extra_read_roots": [],
    "extra_write_roots": [],
}


@dataclass
class Config:
    root: Path
    task_table: Path
    output_dir: Path
    docs_dir: Path
    state_dir: Path
    values: dict = field(default_factory=dict)

    def __getitem__(self, key):
        return self.values[key]

    @property
    def write_roots(self):
        return [self.root, self.output_dir, self.state_dir, Path("/tmp")] + [Path(p).expanduser() for p in self.values["extra_write_roots"]]

    @property
    def read_roots(self):
        system = [Path(p) for p in ("/usr", "/bin", "/opt", "/etc", "/Library", "/System", "/private/var", "/var")]
        return self.write_roots + [self.docs_dir] + system + [Path(p).expanduser() for p in self.values["extra_read_roots"]]


def load(path=None):
    """Read config.json (or the path in RUNNER_CONFIG). Relative paths resolve against the config file."""
    path = Path(path or os.environ.get("RUNNER_CONFIG", "config.json")).expanduser().resolve()
    raw = json.loads(path.read_text())
    base = path.parent

    def rel(name, default):
        return (base / raw.get(name, default)).expanduser().resolve()

    values = {**DEFAULTS, **{k: v for k, v in raw.items() if k in DEFAULTS}}
    return Config(
        root=rel("root", "."),
        task_table=rel("task_table", "tasks.json"),
        output_dir=rel("output_dir", "output"),
        docs_dir=rel("docs_dir", "docs-for-agents"),
        state_dir=rel("state_dir", ".state"),
        values=values,
    )
