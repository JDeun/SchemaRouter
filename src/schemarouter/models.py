from __future__ import annotations

import hashlib
import json
from math import isfinite
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_REMOTE_ADAPTERS = {"mcp", "openapi", "optimade", "html_proposal"}
_LEGACY_ENDPOINT_EXECUTION_METADATA_KEYS = {
    "callable_module",
    "callable_name",
    "entry_type",
    "field_projection",