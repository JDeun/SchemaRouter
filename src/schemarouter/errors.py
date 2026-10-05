class SchemaRouterError(Exception):
    """Base exception for SchemaRouter."""


class RegistrationError(SchemaRouterError):
    """Raised when a tool cannot be registered safely."""


class TraceError(SchemaRouterError):
    """Raised when persisted run-trace data violates the trace contract."""


class StorageFormatError(SchemaRouterError):
    """Raised when persisted SQLite storage cannot be opened or migrated safely."""


class ProposalApprovalError(RegistrationError):
    """Raised when an inferred schema proposal is not safe to approve."""


class ContractAmendmentError(RegistrationError):
    """Raised when a proposed local contract amendment exceeds what is amendable."""


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


class ExecutionInvariantError(ExecutionError):
    """Raised when an internal execution event violates a runtime invariant."""


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


class IndeterminateInvocationError(NonRetryableInvocationError):
    """Raised when an invocation may still complete after timeout or cancellation.

    This is used for side-effecting synchronous work that was offloaded to a worker thread and
    cannot be forcibly stopped once started. Callers must treat the outcome as unknown and must not
    automatically retry the same mutation.
    """


class PostInvocationHookError(NonRetryableInvocationError):
    """Raised when post-invocation processing fails after the tool already succeeded."""

    def __init__(self, message: str, *, result: object) -> None:
        super().__init__(message)
        self.result = result
        self.execution_succeeded = True


class ExecutionHookError(ExecutionError):
    """Raised when a trusted execution hook violates or fails its contract."""


class BindingDriftError(ExecutionError):
    """Raised when an invoker is bound to an older tool schema."""


class SchemaSourceError(SchemaRouterError):
    """Raised when a remote schema source cannot be loaded safely."""


class SchemaNotModifiedError(SchemaSourceError):
    """Raised when a conditional schema fetch returns HTTP 304 Not Modified."""

    def __init__(
        self,
        *,
        validators: dict[str, str] | None = None,
    ) -> None:
        super().__init__("remote schema was not modified")
        self.validators = dict(validators or {})


class SourceProbeDiagnosticError(SchemaSourceError):
    """Raised when a structured-source probe has a safe actionable diagnosis."""

    def __init__(
        self,
        message: str,
        *,
        probe_report: object | None = None,
    ) -> None:
        super().__init__(message)
        self.probe_report = probe_report


class UnsupportedSchemaSourceError(SourceProbeDiagnosticError):
    """Raised when no registered structured-source adapter accepts a URL."""
