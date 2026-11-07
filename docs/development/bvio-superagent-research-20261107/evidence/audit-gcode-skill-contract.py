"""Read-only AST audit. Does not import GCode or execute any Agent/tool."""
import ast
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1]).resolve()
paths = ["gcode/skills/executor.py", "gcode/agent.py", "gcode/tools/load_skill.py"]
trees = {p: ast.parse((root / p).read_text()) for p in paths}
def method(path, cls, name):
    c = next(n for n in trees[path].body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in c.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)

fork = method(paths[0], "SkillExecutor", "execute_fork")
constructor = next(n for n in ast.walk(fork) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "AgentClass")
keywords = {k.arg: ast.unparse(k.value) for k in constructor.keywords}
context = method(paths[0], "SkillExecutor", "_build_fork_context")
cuts = [ast.unparse(n) for n in ast.walk(context) if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Slice) and isinstance(n.slice.upper, ast.Constant) and n.slice.upper.value == 200]
load = method(paths[2], "LoadSkill", "execute")
loads_inline = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "activate_skill" for n in ast.walk(load))
uses_mode = any(isinstance(n, ast.Attribute) and n.attr == "mode" for n in ast.walk(load))
report = {
    "observed_utc": datetime.now(timezone.utc).isoformat(),
    "type": "read-only AST contract audit, not runtime exploitation or end-to-end test",
    "source_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
    "fork_constructor_line": constructor.lineno,
    "constructor_argument_names": sorted(keywords),
    "permission_checker_literal_none": keywords.get("permission_checker") == "None",
    "explicit_max_total_tokens_argument": "max_total_tokens" in keywords,
    "post_constructor_token_budget_assignment": any(isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store) and n.attr == "token_budget" for n in ast.walk(fork)),
    "parent_hooks_passed": "hook_engine" in keywords,
    "full_context_200_character_slice_present": bool(cuts),
    "LoadSkill_activates_inline": loads_inline,
    "LoadSkill_reads_mode": uses_mode,
    "not_tested": ["actual provider calls", "actual tool execution", "authorization bypass exploitation", "runtime throughput", "successful framework integration"],
}
print(json.dumps(report, ensure_ascii=False, indent=2))
