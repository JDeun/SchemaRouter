from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Literal

from .errors import PolicyViolationError
from .models import EndpointSpec, ToolCall, ToolSpec

ApprovalMode = Literal["never", "non_read_only", "all"]
PolicyEffect = Literal["allow", "deny", "require_approval"]
ApprovalCallback = Callable[
    [ToolSpec, EndpointSpec, ToolCall],
    bool | Awaitable[bool],
]


def is_remote_tool(tool: ToolSpec) -> bool:
    return bool(tool.metadata.get("remote")) or tool.metadata.get("adapter") in {
        "mcp",
        "openapi",
        "html_proposal",
    }


@dataclass(frozen=True)
class PolicyRule:
    """Trusted local operation rule.

    The operation pattern uses shell-style wildcard matching against tool.endpoint. Rules are
    evaluated in declaration order and the first matching rule wins. Optional side-effect
    predicates constrain a pattern without exposing credentials or model-visible policy state.
    """

    effect: PolicyEffect
    operation: str = "*"
    name: str | None = None
    remote: bool | None = None
    read_only: bool | None = None
    destructive: bool | None = None

    def __post_init__(self) -> None:
        if self.effect not in {"allow", "deny", "require_approval"}:
            raise ValueError("policy rule effect must be allow, deny, or require_approval")
        if not self.operation.strip():
            raise ValueError("policy rule operation pattern must be non-empty")

    def matches(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
    ) -> bool:
        operation = f"{call.tool}.{call.endpoint}"
        if not fnmatchcase(operation, self.operation):
            return False
        if self.remote is not None and is_remote_tool(tool) != self.remote:
            return False
        if self.read_only is not None and endpoint.read_only is not self.read_only:
            return False
        if self.destructive is not None and endpoint.destructive is not self.destructive:
            return False
        return True


@dataclass(frozen=True)
class PolicyDecision:
    """Resolved local authority for one concrete tool call."""

    effect: PolicyEffect
    source: Literal["rule", "default"]
    operation: str
    rule_name: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class ExecutionPolicy:
    """Local execution authority for side effects and optional per-call approval.

    Fine-grained rules are trusted local configuration and are evaluated before the legacy category
    switches. Existing allow_* flags remain the default behavior when no rule matches.
    """

    allow_mutations: bool = False
    allow_destructive: bool = False
    allow_unclassified_remote: bool = False
    approval_mode: ApprovalMode = "never"
    rules: tuple[PolicyRule, ...] = ()

    def __post_init__(self) -> None:
        if self.approval_mode not in {"never", "non_read_only", "all"}:
            raise ValueError("approval_mode must be 'never', 'non_read_only', or 'all'")
        object.__setattr__(self, "rules", tuple(self.rules))

    def _matching_rule(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
    ) -> PolicyRule | None:
        return next(
            (
                rule
                for rule in self.rules
                if rule.matches(tool, endpoint, call)
            ),
            None,
        )

    def evaluate(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
    ) -> PolicyDecision:
        """Resolve authority without executing the call.

        A matching trusted rule may narrow or explicitly grant authority. If no rule matches, the
        historical category-level fail-closed behavior is preserved.
        """

        operation = f"{call.tool}.{call.endpoint}"
        rule = self._matching_rule(tool, endpoint, call)
        if rule is not None:
            return PolicyDecision(
                effect=rule.effect,
                source="rule",
                operation=operation,
                rule_name=rule.name,
                reason=(
                    f"matched local policy rule {rule.name!r}"
                    if rule.name
                    else f"matched local policy rule {rule.operation!r}"
                ),
            )

        if endpoint.destructive is True and not self.allow_destructive:
            return PolicyDecision(
                effect="deny",
                source="default",
                operation=operation,
                reason=(
                    f"destructive operation {operation} requires allow_destructive=True"
                ),
            )

        if endpoint.read_only is False and not self.allow_mutations:
            return PolicyDecision(
                effect="deny",
                source="default",
                operation=operation,
                reason=f"mutating operation {operation} requires allow_mutations=True",
            )

        if (
            endpoint.read_only is None
            and is_remote_tool(tool)
            and not self.allow_unclassified_remote
        ):
            return PolicyDecision(
                effect="deny",
                source="default",
                operation=operation,
                reason=(
                    f"remote operation {operation} has unclassified side effects; "
                    "set allow_unclassified_remote=True or provide a trusted local contract"
                ),
            )

        return PolicyDecision(
            effect="allow",
            source="default",
            operation=operation,
            reason="allowed by local execution policy",
        )

    def requires_approval(
        self,
        endpoint: EndpointSpec,
        *,
        tool: ToolSpec | None = None,
        call: ToolCall | None = None,
    ) -> bool:
        if tool is not None and call is not None:
            decision = self.evaluate(tool, endpoint, call)
            if decision.effect == "require_approval":
                return True

        if self.approval_mode == "all":
            return True
        if self.approval_mode == "non_read_only":
            return endpoint.read_only is not True
        return False

    def validate(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
    ) -> None:
        decision = self.evaluate(tool, endpoint, call)
        if decision.effect == "deny":
            raise PolicyViolationError(decision.reason)
