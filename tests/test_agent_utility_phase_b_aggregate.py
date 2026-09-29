from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.aggregate_agent_utility_phase_b import (
    _cluster_bootstrap_delta,
    _retrieval_coverage,
    aggregate,
)


