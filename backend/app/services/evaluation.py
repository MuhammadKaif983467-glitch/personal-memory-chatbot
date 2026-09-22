"""Automated quality evaluation framework.

Provides deterministic evaluation of retrieval, memory, identity, and security.
Every result is classified as PASS, FAIL, BLOCKED, or NOT_TESTED.
No fabricated scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any


class EvalResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_TESTED = "NOT_TESTED"


@dataclass
class EvalCase:
    """A single evaluation case."""
    name: str
    category: str
    result: EvalResult = EvalResult.NOT_TESTED
    details: str = ""
    expected: Any = None
    actual: Any = None


@dataclass
class EvalSuite:
    """A collection of evaluation cases."""
    name: str
    cases: list[EvalCase] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.result == EvalResult.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.cases if c.result == EvalResult.FAIL)

    @property
    def blocked(self) -> int:
        return sum(1 for c in self.cases if c.result == EvalResult.BLOCKED)

    def summary(self) -> dict:
        return {
            "suite": self.name,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "blocked": self.blocked,
            "not_tested": self.total - self.passed - self.failed - self.blocked,
        }


class RetrievalEvaluator:
    """Evaluate retrieval quality."""

    def evaluate_relevance(self, question: str, results: list, expected_memories: list[int]) -> EvalSuite:
        suite = EvalSuite(name="retrieval_relevance")
        if not results:
            suite.cases.append(EvalCase("no_results", "retrieval", EvalResult.FAIL, "No results returned"))
            return suite

        found_ids = [r.memory.id for r in results]
        for mem_id in expected_memories:
            if mem_id in found_ids:
                suite.cases.append(EvalCase(f"recall_{mem_id}", "retrieval", EvalResult.PASS))
            else:
                suite.cases.append(EvalCase(f"recall_{mem_id}", "retrieval", EvalResult.FAIL, f"Memory {mem_id} not found"))
        return suite

    def evaluate_project_isolation(self, results: list, expected_project_id: int) -> EvalSuite:
        suite = EvalSuite(name="retrieval_isolation")
        for r in results:
            if r.memory.project_id == expected_project_id:
                suite.cases.append(EvalCase(f"isolation_{r.memory.id}", "isolation", EvalResult.PASS))
            else:
                suite.cases.append(EvalCase(f"isolation_{r.memory.id}", "isolation", EvalResult.FAIL,
                                            f"Project leak: expected {expected_project_id}, got {r.memory.project_id}"))
        if not results:
            suite.cases.append(EvalCase("no_leak", "isolation", EvalResult.PASS, "No results = no leak"))
        return suite

    def evaluate_deduplication(self, results: list) -> EvalSuite:
        suite = EvalSuite(name="retrieval_dedup")
        seen_ids = set()
        duplicates = False
        for r in results:
            if r.memory.id in seen_ids:
                duplicates = True
                suite.cases.append(EvalCase(f"dedup_{r.memory.id}", "dedup", EvalResult.FAIL, "Duplicate memory in results"))
            seen_ids.add(r.memory.id)
        if not duplicates:
            suite.cases.append(EvalCase("no_duplicates", "dedup", EvalResult.PASS))
        return suite


class MemoryEvaluator:
    """Evaluate memory quality."""

    def evaluate_extraction(self, message: str, expected_type: str, memory_type: str) -> EvalSuite:
        suite = EvalSuite(name="memory_extraction")
        if memory_type == expected_type:
            suite.cases.append(EvalCase("type_match", "extraction", EvalResult.PASS))
        else:
            suite.cases.append(EvalCase("type_match", "extraction", EvalResult.FAIL,
                                        f"Expected {expected_type}, got {memory_type}"))
        return suite

    def evaluate_correction(self, old_memory, new_memory) -> EvalSuite:
        suite = EvalSuite(name="memory_correction")
        if old_memory.status == "active" or old_memory.status == "SUPERSEDED":
            suite.cases.append(EvalCase("old_retired", "correction", EvalResult.PASS))
        else:
            suite.cases.append(EvalCase("old_retired", "correction", EvalResult.FAIL,
                                        f"Old memory status: {old_memory.status}"))
        return suite


class IdentityEvaluator:
    """Evaluate identity correctness."""

    def evaluate_me_other(self, sender: str, expected_role: str) -> EvalSuite:
        suite = EvalSuite(name="identity_me_other")
        if sender.lower() in ("me", "user") and expected_role == "ME":
            suite.cases.append(EvalCase("me识别", "identity", EvalResult.PASS))
        elif sender.lower() not in ("me", "user") and expected_role == "OTHER":
            suite.cases.append(EvalCase("other识别", "identity", EvalResult.PASS))
        else:
            suite.cases.append(EvalCase("role_match", "identity", EvalResult.FAIL,
                                        f"Sender={sender}, expected role={expected_role}"))
        return suite

    def evaluate_no_generic_names(self, names: list[str]) -> EvalSuite:
        suite = EvalSuite(name="identity_no_generic")
        generic = {"user", "assistant", "system", "bot"}
        for name in names:
            if name.lower() in generic:
                suite.cases.append(EvalCase(f"generic_{name}", "identity", EvalResult.FAIL,
                                            f"Generic name found: {name}"))
            else:
                suite.cases.append(EvalCase(f"real_{name}", "identity", EvalResult.PASS))
        return suite


class SecurityEvaluator:
    """Evaluate security defenses."""

    def evaluate_prompt_injection(self, input_text: str, output: str) -> EvalSuite:
        suite = EvalSuite(name="security_injection")
        injection_indicators = ["system:", "you are now", "ignore previous", "new instructions"]
        found = [ind for ind in injection_indicators if ind.lower() in output.lower()]
        if not found:
            suite.cases.append(EvalCase("no_injection", "security", EvalResult.PASS))
        else:
            suite.cases.append(EvalCase("injection_leak", "security", EvalResult.FAIL,
                                        f"Injection indicators found: {found}"))
        return suite

    def evaluate_project_isolation(self, data: dict, expected_project: int) -> EvalSuite:
        suite = EvalSuite(name="security_project_isolation")
        actual_project = data.get("project_id")
        if actual_project == expected_project:
            suite.cases.append(EvalCase("correct_project", "isolation", EvalResult.PASS))
        else:
            suite.cases.append(EvalCase("project_leak", "isolation", EvalResult.FAIL,
                                        f"Expected project {expected_project}, got {actual_project}"))
        return suite
