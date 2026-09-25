class SchemaRouterError(Exception):
    """Base exception for SchemaRouter."""


class RegistrationError(SchemaRouterError):
    """Raised when a tool cannot be registered safely."""


class TraceError(SchemaRouterError):
    """Raised when persisted run-trace data violates the trace contract."""


class ProposalApprovalError(RegistrationError):
    """Raised when an inferred schema proposal is not safe to approve."""


class PlanningError(SchemaRouterError):
    """Raised when a plan cannot be produced."""


class ModelAnalysisError(PlanningError):
    """Raised when model-assisted query analysis fails validation."""


class PlanValidationError(SchemaRouterError):
    """Raised when an execution plan violates the current schema."""


class PolicyViolationError(PlanValidationError):
    """Raised when local execution policy denies a tool call."""


class ApprovalDeniedError(PolicyViolationError):
    """Raised when a call requiring trusted local approval is not approved."""


class ExecutionBudgetExceededError(PolicyViolationError):
    """Raised before execution would exceed a trusted local run budget."""


class SchemaDriftError(PlanValidationError):
    """Raised when a plan was compiled against an older endpoint schema."""


class SchemaValidationError(PlanValidationError):
    """Raised when arguments or tool output violate a declared JSON Schema."""


class ExecutionError(SchemaRouterError):
    """Raised when tool invocation fails."""


class RequiredFieldUnavailableError(ExecutionError):
    """Raised when a valid response cannot satisfy a compiled semantic field requirement.

    This is eligible for bounded read-only fallback but does not mark the access path unhealthy,
    because request-specific data absence is not a transport outage.
    """


class InvocationUnavailableError(ExecutionError, RuntimeError):
    """Raised when an otherwise valid access path is temporarily unavailable.

    Executors may retry the same read-only route and a precompiled fallback route may use this
    marker to move to another trusted access path. Policy/schema/authorization failures must never
    be translated to this error.
    """


class NonRetryableInvocationError(ExecutionError, RuntimeError):
    """Raised when repeating the same invocation cannot safely recover.

    Also remains a RuntimeError for compatibility with built-in invoker callers that historically
    caught deterministic runtime failures directly.
    """


class ExecutionHookError(ExecutionError):
    """Raised when a trusted execution hook violates or fails its contract."""


class BindingDriftError(ExecutionError):
    """Raised when an invoker is bound to an older tool schema."""


class SchemaSourceError(SchemaRouterError):
    """Raised when a remote schema source cannot be loaded safely."""


class UnsupportedSchemaSourceError(SchemaSourceError):
    """Raised when no registered structured-source adapter accepts a URL."""
