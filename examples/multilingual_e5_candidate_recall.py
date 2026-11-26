"""Historical research-only multilingual candidate recall without tool execution.

Install explicitly: pip install sentence-transformers
Run from a source checkout: python -m examples.multilingual_e5_candidate_recall

The first run can download model weights. The imported SchemaRouter core does
not download models or require Torch/sentence-transformers. This example
demonstrates *recall*, not a calibrated no-match or agent-success result.

한국어·일본어 질의를 영어 도구 설명과 검색하는 로컬 E5 예제입니다.
임베딩 점수는 실행 권한이나 신뢰할 수 있는 no-match 확률이 아닙니다.
"""
from __future__ import annotations

from schemarouter import (
    E5CachedEmbedder,
    EmbeddingDecisionBackend,
    EndpointSpec,
    InMemoryRegistry,
    ToolSpec,
)
from scripts.research_legacy_decision_policy import LegacyDecisionPlanner


def main() -> None:
    from sentence_transformers import SentenceTransformer

    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="materials",
            description="Search a collection of material properties",
            endpoints=[
                EndpointSpec(
                    name="search",
                    description="Look up band gap and formation energies",
                    read_only=True,
                )
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="flights",
            description="Search airline flights",
            endpoints=[EndpointSpec(name="search", read_only=True)],
        )
    )

    # Host owns the model and explicitly permits any first-run download.
    model = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")

    def encode(texts: list[str]) -> list[list[float]]:
        return model.encode(
            texts, batch_size=32, normalize_embeddings=True,
        ).tolist()

    # Reusing the instance caches candidate passages, not changing queries.
    embedder = E5CachedEmbedder(encode, max_cached_passages=2048)
    recall = EmbeddingDecisionBackend(embedder)

    planner = LegacyDecisionPlanner(
        registry,
        candidate_recall_backend=recall,
        candidate_recall_limit=2,
    )

    for query in ("Find material properties", "재료 물성을 찾아줘", "材料の物性を調べたい"):
        plan = planner.plan(query)
        print(query, [(call.tool, call.endpoint) for call in plan.calls])

    # Do not treat the top cosine similarity as a calibrated 'can execute'
    # probability. Evaluate supported / unsupported cohorts before gating
    # any actual calls, and retain SchemaRouter authorization at execution.


if __name__ == "__main__":
    main()
