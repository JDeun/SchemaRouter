class SchemaRouterError(Exception):
    """Base exception for SchemaRouter."""


class RegistrationError(SchemaRouterError):
    """Raised when a tool cannot be registered safely."""


class ProposalApprovalError(RegistrationError):
    """Raised when an inferred schema proposal is not safe to approve."""


class PlanningError(SchemaRouterError):
    """Raised when a plan cannot be produced."""


class ModelAnalysisError(PlanningError):
    """Raised when model-assisted query analysis fails validation."""


class PlanValidationError(SchemaRouterError):
    """Raised when an execution plan violates the current schema."""


class SchemaDriftError(PlanValidationError):
    """Raised when a plan was compiled against an older endpoint schema."""


class ExecutionError(SchemaRouterError):
    """Raised when tool invocation fails."""


class SchemaSourceError(SchemaRouterError):
    """Raised when a remote schema source cannot be loaded safely."""


class UnsupportedSchemaSourceError(SchemaSourceError):
    """Raised when a URL is neither a supported OpenAPI document nor an MCP server."""
