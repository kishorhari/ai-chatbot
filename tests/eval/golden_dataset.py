"""A deterministic golden dataset and pure retrieval metrics (M3.8).

This is the fixed evaluation set behind Milestone 3's *retrieval quality gate*
(roadmap §7, criterion 8). It is intentionally small, hand-labelled, and
committed to source control so the gate is **reproducible**: the same corpus and
queries produce the same recall on every run, on every machine, with no network
or model — because the offline path (the deterministic ``FakeEmbeddingProvider``
+ ``InMemoryVectorStore``) is fully reproducible.

The corpus is six documents on lexically disjoint topics; each labelled query
reuses that topic's distinctive vocabulary. The reference embedding is lexical
(hashing bag-of-words), so a query is expected to retrieve its own topic's
document ahead of the others. This measures the *retrieval mechanism* end to end
(chunk → embed → store → embed-query → search → rank), not semantic quality — the
fake embedding is not a semantic model, and this file says so plainly.

Nothing here imports application or infrastructure code: the dataset and the
metric functions are pure data and pure functions, so they can be reused by any
harness (the pytest gate in ``test_retrieval_eval.py``, or an ad-hoc script).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class GoldenDocument:
    """One corpus document with a stable ``source`` id and a topic label."""

    source: str
    topic: str
    text: str


@dataclass(frozen=True, slots=True)
class GoldenQuery:
    """A labelled query: the sources whose content should answer it."""

    query: str
    relevant_sources: frozenset[str]
    topic: str
    note: str = ""


# --- The corpus: six lexically disjoint topics -----------------------------
# Distinct distinctive vocabulary per topic (jupiter, sourdough, dividends,
# chlorophyll, compiler, nile) so lexical similarity is discriminative.
GOLDEN_DOCUMENTS: tuple[GoldenDocument, ...] = (
    GoldenDocument(
        source="astronomy.md",
        topic="science",
        text=(
            "The Sun is a star at the centre of the Solar System. The planets orbit "
            "the Sun along elliptical paths. Jupiter is the largest planet, a gas "
            "giant encircled by dozens of moons and a faint ring."
        ),
    ),
    GoldenDocument(
        source="cooking.md",
        topic="lifestyle",
        text=(
            "Sourdough bread relies on a fermented starter of flour and water. The "
            "wild yeast in the starter leavens the dough over many hours, producing "
            "a tangy, open crumb and a dark crust when baked in a very hot oven."
        ),
    ),
    GoldenDocument(
        source="finance.md",
        topic="business",
        text=(
            "A share of stock represents partial ownership of a company. "
            "Shareholders may receive dividends from profits, and the share price "
            "fluctuates with supply and demand as the stock trades on an exchange."
        ),
    ),
    GoldenDocument(
        source="biology.md",
        topic="science",
        text=(
            "Photosynthesis lets green plants convert sunlight, water, and carbon "
            "dioxide into glucose and oxygen. Chlorophyll in the leaves captures the "
            "light energy that drives the reaction inside the chloroplasts."
        ),
    ),
    GoldenDocument(
        source="computing.md",
        topic="technology",
        text=(
            "A compiler translates source code written in a high-level programming "
            "language into machine instructions. An optimising compiler rewrites the "
            "generated binary so the compiled program runs faster at execution time."
        ),
    ),
    GoldenDocument(
        source="geography.md",
        topic="science",
        text=(
            "The Nile is a major river in Africa, flowing north through Egypt into "
            "the Mediterranean Sea. For millennia its annual flood has watered "
            "agriculture along the fertile banks of the river valley."
        ),
    ),
)


# --- The labelled queries --------------------------------------------------
GOLDEN_QUERIES: tuple[GoldenQuery, ...] = (
    GoldenQuery(
        query="Which planet is the largest gas giant orbiting the Sun?",
        relevant_sources=frozenset({"astronomy.md"}),
        topic="science",
        note="distinctive: jupiter, gas giant, orbit",
    ),
    GoldenQuery(
        query="How does a sourdough starter leaven bread dough?",
        relevant_sources=frozenset({"cooking.md"}),
        topic="lifestyle",
        note="distinctive: sourdough, starter, leaven",
    ),
    GoldenQuery(
        query="What dividends do shareholders who own stock receive?",
        relevant_sources=frozenset({"finance.md"}),
        topic="business",
        note="distinctive: dividends, shareholders, stock",
    ),
    GoldenQuery(
        query="How do plants use chlorophyll during photosynthesis?",
        relevant_sources=frozenset({"biology.md"}),
        topic="science",
        note="distinctive: chlorophyll, photosynthesis, leaves",
    ),
    GoldenQuery(
        query="What does a compiler do with source code?",
        relevant_sources=frozenset({"computing.md"}),
        topic="technology",
        note="distinctive: compiler, source code, machine instructions",
    ),
    GoldenQuery(
        query="Which African river flows through Egypt into the Mediterranean?",
        relevant_sources=frozenset({"geography.md"}),
        topic="science",
        note="distinctive: nile, egypt, mediterranean, river",
    ),
)


# --- Pure metrics ----------------------------------------------------------
# `retrieved` is the ranked list of source ids a query returned, most-relevant
# first; `relevant` is the labelled truth set. These are deliberately
# dependency-free so any harness can score a run.


@dataclass(frozen=True, slots=True)
class QueryEvaluation:
    """The scored outcome of one query against the golden labels."""

    query: str
    relevant: frozenset[str]
    retrieved: tuple[str, ...]
    k: int

    @property
    def recall_at_k(self) -> float:
        """Fraction of the relevant sources found within the top ``k``."""
        top = set(self.retrieved[: self.k])
        return len(self.relevant & top) / len(self.relevant)

    @property
    def hit_at_k(self) -> bool:
        """Whether at least one relevant source is within the top ``k``."""
        return bool(self.relevant & set(self.retrieved[: self.k]))

    @property
    def reciprocal_rank(self) -> float:
        """1/rank of the first relevant source (0.0 if none retrieved)."""
        for position, source in enumerate(self.retrieved, start=1):
            if source in self.relevant:
                return 1.0 / position
        return 0.0


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Aggregate metrics over every scored query."""

    k: int
    evaluations: tuple[QueryEvaluation, ...] = field(default_factory=tuple)

    @property
    def mean_recall_at_k(self) -> float:
        """Mean recall@k across all queries (0.0 for an empty set)."""
        if not self.evaluations:
            return 0.0
        return sum(e.recall_at_k for e in self.evaluations) / len(self.evaluations)

    @property
    def hit_rate_at_k(self) -> float:
        """Fraction of queries with at least one relevant result in the top ``k``."""
        if not self.evaluations:
            return 0.0
        return sum(1 for e in self.evaluations if e.hit_at_k) / len(self.evaluations)

    @property
    def mean_reciprocal_rank(self) -> float:
        """Mean reciprocal rank of the first relevant result across queries."""
        if not self.evaluations:
            return 0.0
        return sum(e.reciprocal_rank for e in self.evaluations) / len(self.evaluations)

    def misses(self) -> tuple[QueryEvaluation, ...]:
        """The queries that did not surface a relevant source in the top ``k``."""
        return tuple(e for e in self.evaluations if not e.hit_at_k)


def evaluate_query(
    *, query: str, relevant: frozenset[str], retrieved: Sequence[str], k: int
) -> QueryEvaluation:
    """Score one query's ranked ``retrieved`` sources against ``relevant``."""
    return QueryEvaluation(query=query, relevant=relevant, retrieved=tuple(retrieved), k=k)


def build_report(evaluations: Sequence[QueryEvaluation], *, k: int) -> EvaluationReport:
    """Aggregate per-query evaluations into a report."""
    return EvaluationReport(k=k, evaluations=tuple(evaluations))
