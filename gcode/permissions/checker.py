from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from gcode.permissions.dangerous import DangerousCommandDetector, is_safe_command
from gcode.permissions.modes import DecisionEffect, PermissionMode, mode_decide
from gcode.permissions.rules import RuleEngine, extract_content
from gcode.permissions.sandbox import PathSandbox
from gcode.tools.base import Tool

_PLAN_MODE_ALLOWED_TOOLS = frozenset(
    {"Agent", "ToolSearch", "AskUserQuestion", "ExitPlanMode"}
)


@dataclass
class Decision:
    effect: DecisionEffect
    reason: str


class PermissionChecker:
    def __init__(
        self,
        detector: DangerousCommandDetector,
        sandbox: PathSandbox,
        rule_engine: RuleEngine,
        mode: PermissionMode = PermissionMode.DEFAULT,
    ) -> None:
        self.detector = detector
        self.sandbox = sandbox
        self.rule_engine = rule_engine
        self.mode = mode
        self.plan_file_path: str = ""

    def check(self, tool: Tool, arguments: dict[str, Any]) -> Decision:
        content = extract_content(tool.name, arguments)

        # Explicit denial applies before plan exceptions and automatic commands.
        rule_result = self.rule_engine.evaluate(tool.name, content)
        if rule_result == "deny":
            return Decision(effect="deny", reason="权限规则拒绝")

        if tool.category == "command":
            hit, reason = self.detector.detect(content)
            if hit:
                return Decision(effect="deny", reason=f"危险命令拦截: {reason}")

        path_content = (
            arguments.get("path", ".") if tool.name in {"Glob", "Grep"} else content
        )
        if tool.category in ("read", "write") and path_content:
            ok, reason = self.sandbox.check(path_content)
            if not ok:
                return Decision(effect="deny", reason=f"路径沙箱拦截: {reason}")

        if self.mode == PermissionMode.PLAN:
            if tool.name in _PLAN_MODE_ALLOWED_TOOLS:
                return Decision(effect="allow", reason="Plan mode: allowed tool")
            if (
                tool.name in ("WriteFile", "EditFile")
                and content
                and self._is_plan_file(content)
            ):
                return Decision(effect="allow", reason="Plan mode: plan file write")
            if tool.category in ("write", "command"):
                return Decision(effect="deny", reason="Plan mode: mutation denied")

        if rule_result == "allow":
            return Decision(effect="allow", reason="权限规则放行")
        if tool.category == "command" and is_safe_command(content or ""):
            return Decision(effect="allow", reason="Safe exact command")

        # Layer 4: 权限模式兜底判定
        effect = mode_decide(self.mode, tool.category)
        if effect == "allow":
            return Decision(effect="allow", reason=f"权限模式 {self.mode.value} 放行")
        if effect == "deny":
            return Decision(effect="deny", reason=f"权限模式 {self.mode.value} 拒绝")

        # Layer 5: 触发人工确认（HITL）
        return Decision(effect="ask", reason="需要用户确认")

    def _is_plan_file(self, target_path: str) -> bool:
        if not self.plan_file_path or not target_path:
            return False
        try:
            from pathlib import Path

            target = Path(target_path).expanduser()
            if not target.is_absolute():
                target = self.sandbox.project_root / target
            return (
                target.resolve() == Path(self.plan_file_path).resolve()
                and self.sandbox.check(str(target))[0]
            )
        except (OSError, ValueError):
            return False
