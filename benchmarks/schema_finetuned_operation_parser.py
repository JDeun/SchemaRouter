"""End-to-end multilingual operation/OOS parser for V6H / #415.

The model is trained only on the frozen generic naturalistic bank. At runtime it
has veto-only authority: frozen BGE-M3 chooses the registered positive route,
while the parser may preserve that exact route or return NO_ROUTE.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any

from benchmarks.schema_adb_baseline import (
    ACTION_WEIGHT,
    SCHEMA_WEIGHT,
    _action_text,
    _cosine,
    _schema_text,
    _to_vectors,
    compile_registry_contracts,
)
from benchmarks.schema_naturalistic_operation_probe import (
    BACKGROUND,
    BANK_PATH,
    MINILM_MODEL,
    MINILM_REVISION,
    TOOL_OPERATION,
    load_naturalistic_bank,
)

TRAINING_SEED = 20260929
MAX_LENGTH = 96
BATCH_SIZE = 32
EPOCHS = 4
LEARNING_RATE = 2e-5
WEIGHT_DECAY = 0.01
GRAD_CLIP_NORM = 1.0

OPERATION_LABELS = (
    "search",
    "retrieve",
    "list",
    "create",
    "update",
    "delete",
    "cancel",
    "refund",
    "send",
    "share",
    "export",
    "translate",
    "summarize",
    "compare",
    "merge",
    "restart",
    "execute",
    "forecast",
)
SCOPE_LABELS = (TOOL_OPERATION, BACKGROUND)

_OPERATION_TO_ID = {label: index for index, label in enumerate(OPERATION_LABELS)}
_SCOPE_TO_ID = {label: index for index, label in enumerate(SCOPE_LABELS)}


def training_bank_sha256(path: Path = BANK_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_training_rows() -> list[dict[str, Any]]:
    bank = load_naturalistic_bank()
    if tuple(bank.operation_labels) != OPERATION_LABELS:
        raise ValueError("operation label order drifted")

    rows: list[dict[str, Any]] = []
    for text, target in zip(
        bank.operation_texts,
        bank.operation_targets,
        strict=True,
    ):
        rows.append(
            {
                "text": text,
                "scope_id": _SCOPE_TO_ID[TOOL_OPERATION],
                "operation_id": _OPERATION_TO_ID[target],
            }
        )
    for text in bank.background_texts:
        rows.append(
            {
                "text": text,
                "scope_id": _SCOPE_TO_ID[BACKGROUND],
                "operation_id": -100,
            }
        )
    if len(rows) != 816:
        raise ValueError("V6H training row count drifted")
    return rows


def _seed_everything() -> None:
    import numpy as np
    import torch

    random.seed(TRAINING_SEED)
    np.random.seed(TRAINING_SEED)
    torch.manual_seed(TRAINING_SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(TRAINING_SEED)


def _mean_pool(last_hidden_state: Any, attention_mask: Any) -> Any:
    import torch

    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    summed = torch.sum(last_hidden_state * mask, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts


def build_multitask_model(device: str = "cpu") -> Any:
    import torch
    from transformers import AutoModel

    class MultiTaskOperationModel(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = AutoModel.from_pretrained(
                MINILM_MODEL,
                revision=MINILM_REVISION,
                trust_remote_code=False,
            )
            hidden = int(self.encoder.config.hidden_size)
            self.scope_head = torch.nn.Linear(hidden, len(SCOPE_LABELS))
            self.operation_head = torch.nn.Linear(hidden, len(OPERATION_LABELS))

        def forward(self, **inputs: Any) -> tuple[Any, Any]:
            outputs = self.encoder(**inputs)
            pooled = _mean_pool(
                outputs.last_hidden_state,
                inputs["attention_mask"],
            )
            return self.scope_head(pooled), self.operation_head(pooled)

    return MultiTaskOperationModel().to(device)


def load_tokenizer() -> Any:
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(
        MINILM_MODEL,
        revision=MINILM_REVISION,
        trust_remote_code=False,
    )


def train_multitask_model(
    *,
    device: str = "cpu",
) -> tuple[Any, Any, list[dict[str, float]]]:
    import torch
    import torch.nn.functional as functional

    _seed_everything()
    rows = load_training_rows()
    tokenizer = load_tokenizer()
    model = build_multitask_model(device=device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )
    generator = torch.Generator(device="cpu")
    generator.manual_seed(TRAINING_SEED)

    epoch_history: list[dict[str, float]] = []
    model.train()
    for epoch in range(EPOCHS):
        permutation = torch.randperm(len(rows), generator=generator).tolist()
        total_loss = 0.0
        total_scope_loss = 0.0
        total_operation_loss = 0.0
        steps = 0

        for start in range(0, len(permutation), BATCH_SIZE):
            indices = permutation[start : start + BATCH_SIZE]
            batch = [rows[index] for index in indices]
            encoded = tokenizer(
                [str(row["text"]) for row in batch],
                padding=True,
                truncation=True,
                max_length=MAX_LENGTH,
                return_tensors="pt",
            )
            encoded = {
                key: value.to(device)
                for key, value in encoded.items()
            }
            scope_targets = torch.tensor(
                [int(row["scope_id"]) for row in batch],
                dtype=torch.long,
                device=device,
            )
            operation_targets = torch.tensor(
                [int(row["operation_id"]) for row in batch],
                dtype=torch.long,
                device=device,
            )

            optimizer.zero_grad(set_to_none=True)
            scope_logits, operation_logits = model(**encoded)
            scope_loss = functional.cross_entropy(
                scope_logits,
                scope_targets,
            )
            operation_mask = operation_targets != -100
            if bool(operation_mask.any()):
                operation_loss = functional.cross_entropy(
                    operation_logits[operation_mask],
                    operation_targets[operation_mask],
                )
            else:
                operation_loss = operation_logits.sum() * 0.0
            loss = scope_loss + operation_loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                GRAD_CLIP_NORM,
            )
            optimizer.step()

            total_loss += float(loss.detach().cpu())
            total_scope_loss += float(scope_loss.detach().cpu())
            total_operation_loss += float(operation_loss.detach().cpu())
            steps += 1

        epoch_history.append(
            {
                "epoch": float(epoch + 1),
                "loss": total_loss / steps,
                "scope_loss": total_scope_loss / steps,
                "operation_loss": total_operation_loss / steps,
            }
        )

    model.eval()
    return model, tokenizer, epoch_history


def save_trained_state(model: Any, path: Path) -> str:
    import torch

    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_trained_state(path: Path, *, device: str = "cpu") -> tuple[Any, Any]:
    import torch

    tokenizer = load_tokenizer()
    model = build_multitask_model(device=device)
    state = torch.load(path, map_location=device, weights_only=True)
    model.load_state_dict(state, strict=True)
    model.eval()
    return model, tokenizer


def predict_structure(
    model: Any,
    tokenizer: Any,
    query: str,
    *,
    device: str = "cpu",
) -> dict[str, str]:
    import torch

    encoded = tokenizer(
        [query],
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    encoded = {key: value.to(device) for key, value in encoded.items()}
    with torch.inference_mode():
        scope_logits, operation_logits = model(**encoded)
    scope_id = int(scope_logits.argmax(dim=-1).item())
    operation_id = int(operation_logits.argmax(dim=-1).item())
    return {
        "scope_class": SCOPE_LABELS[scope_id],
        "operation_class": OPERATION_LABELS[operation_id],
    }


def apply_structured_membership(
    *,
    raw_top_route: str,
    scope_class: str,
    operation_class: str,
    supported_leaves: set[str],
    unknown_tool: bool,
) -> tuple[str | None, str]:
    if unknown_tool:
        return raw_top_route, "unknown_operation_semantics_preserve"
    if scope_class == BACKGROUND:
        return None, "background_parser_veto"
    if scope_class != TOOL_OPERATION:
        raise ValueError(f"unexpected scope class: {scope_class}")
    if operation_class not in supported_leaves:
        return None, "unsupported_operation_parser_veto"
    return raw_top_route, "registered_operation_parser_preserve"


class FineTunedOperationMembershipRouter:
    def __init__(
        self,
        registry: Any,
        bge_embedder: Any,
        parser_model: Any,
        tokenizer: Any,
        *,
        device: str = "cpu",
    ) -> None:
        self.registry = registry
        self.bge_embedder = bge_embedder
        self.parser_model = parser_model
        self.tokenizer = tokenizer
        self.device = device
        self.contracts = compile_registry_contracts(registry)

        route_specs: dict[str, tuple[str, str]] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route_id = f"{tool.key}.{endpoint.name}"
                route_specs[route_id] = (
                    _schema_text(tool, endpoint),
                    _action_text(endpoint),
                )
        if set(route_specs) != set(self.contracts):
            raise ValueError("route and contract sets differ")
        self.route_ids = tuple(sorted(route_specs))

        route_count = len(self.route_ids)
        route_vectors = _to_vectors(
            bge_embedder(
                [
                    *(route_specs[route][0] for route in self.route_ids),
                    *(route_specs[route][1] for route in self.route_ids),
                ]
            )
        )
        if len(route_vectors) != route_count * 2:
            raise ValueError("unexpected route embedding count")
        self.schema_vectors = dict(
            zip(self.route_ids, route_vectors[:route_count], strict=True)
        )
        self.action_vectors = dict(
            zip(self.route_ids, route_vectors[route_count:], strict=True)
        )

        by_tool: dict[str, list[Any]] = {}
        for contract in self.contracts.values():
            by_tool.setdefault(contract.tool_key, []).append(contract)
        self.unknown_tools: set[str] = set()
        self.supported_leaves: dict[str, frozenset[str]] = {}
        for tool_key, contracts in by_tool.items():
            if any(contract.leaf is None for contract in contracts):
                self.unknown_tools.add(tool_key)
            else:
                self.supported_leaves[tool_key] = frozenset(
                    str(contract.leaf) for contract in contracts
                )

    def _rank_raw(self, query_vector: list[float]) -> list[tuple[str, float]]:
        rows: list[tuple[str, float]] = []
        for route_id in self.route_ids:
            score = (
                SCHEMA_WEIGHT
                * _cosine(query_vector, self.schema_vectors[route_id])
                + ACTION_WEIGHT
                * _cosine(query_vector, self.action_vectors[route_id])
            )
            rows.append((route_id, score))
        rows.sort(key=lambda item: (-item[1], item[0]))
        return rows

    def route(self, query: str) -> dict[str, Any]:
        bge_vector = _to_vectors(self.bge_embedder([query]))[0]
        raw_ranked = self._rank_raw(bge_vector)
        raw_top_route, raw_top_score = raw_ranked[0]
        raw_tool = self.contracts[raw_top_route].tool_key

        if raw_tool in self.unknown_tools or raw_tool not in self.supported_leaves:
            predicted = raw_top_route
            reason = "unknown_operation_semantics_preserve"
            structure = {
                "scope_class": None,
                "operation_class": None,
            }
        else:
            structure = predict_structure(
                self.parser_model,
                self.tokenizer,
                query,
                device=self.device,
            )
            predicted, reason = apply_structured_membership(
                raw_top_route=raw_top_route,
                scope_class=str(structure["scope_class"]),
                operation_class=str(structure["operation_class"]),
                supported_leaves=set(self.supported_leaves[raw_tool]),
                unknown_tool=False,
            )

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "scope_class": structure["scope_class"],
            "operation_class": structure["operation_class"],
            "supported_leaves": sorted(
                self.supported_leaves.get(raw_tool, ())
            ),
            "reason": reason,
        }


def state_metadata(
    *,
    state_sha256: str,
    epoch_history: list[dict[str, float]],
) -> dict[str, Any]:
    return {
        "model": MINILM_MODEL,
        "revision": MINILM_REVISION,
        "training_bank_sha256": training_bank_sha256(),
        "seed": TRAINING_SEED,
        "max_length": MAX_LENGTH,
        "batch_size": BATCH_SIZE,
        "epochs": EPOCHS,
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "gradient_clip_norm": GRAD_CLIP_NORM,
        "operation_labels": list(OPERATION_LABELS),
        "scope_labels": list(SCOPE_LABELS),
        "state_dict_sha256": state_sha256,
        "epoch_history": epoch_history,
    }


def metadata_sha256(metadata: dict[str, Any]) -> str:
    payload = json.dumps(
        metadata,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def assert_finite_history(history: list[dict[str, float]]) -> None:
    if len(history) != EPOCHS:
        raise ValueError("unexpected epoch history length")
    for row in history:
        if any(not math.isfinite(float(value)) for value in row.values()):
            raise ValueError("non-finite training history")
