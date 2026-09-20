class SchemaRouterError(Exception):
    """Base exception for SchemaRouter."""


class RegistrationError(SchemaRouterError):
    """Raised when a tool cannot be registered safely."""


class PlanningError(SchemaRouterError):
    """Raised when a plan cannot be produced."""


class PlanValidationError(SchemaRouterError):
    """Raised when an execution plan violates the current schema."""


class SchemaDriftError(PlanValidationError):
    """Raised when a plan was compiled against an older endpoint schema."""


class ExecutionError(SchemaRouterError):
    """Raised when tool invocation fails."""
