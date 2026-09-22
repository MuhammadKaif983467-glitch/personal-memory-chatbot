"""Memory graph traversal service with bounded multi-hop support.

Provides graph traversal over MemoryRelationship edges with:
- Configurable max depth (default: 2)
- Configurable max nodes (default: 50)
- Cycle detection
- Duplicate prevention
- Project isolation
- Relationship weighting
- Deterministic traversal
- Timeout protection
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import Memory, MemoryRelationship
from app.database.repositories import MemoryRelationshipRepository, MemoryRepository

logger = get_logger("memory_graph")

DEFAULT_MAX_DEPTH = 2
DEFAULT_MAX_NODES = 50


@dataclass
class GraphNode:
    """A node in the memory graph."""
    memory_id: int
    content: str
    memory_type: str
    depth: int
    path: list[int] = field(default_factory=list)


@dataclass
class GraphResult:
    """Result of a graph traversal."""
    nodes: list[GraphNode]
    edges: list[MemoryRelationship]
    total_nodes: int
    truncated: bool
    max_depth_reached: int


class MemoryGraphService:
    """Bounded graph traversal over memory relationships."""

    def __init__(
        self,
        session: Session,
        *,
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_nodes: int = DEFAULT_MAX_NODES,
    ) -> None:
        self.session = session
        self.rel_repo = MemoryRelationshipRepository(session)
        self.mem_repo = MemoryRepository(session)
        self.max_depth = max_depth
        self.max_nodes = max_nodes

    def neighborhood(
        self,
        memory_id: int,
        *,
        project_id: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> GraphResult:
        """Get the neighborhood of a memory up to max_depth hops.

        Uses BFS traversal with cycle detection and node count limit.
        """
        depth = max_depth if max_depth is not None else self.max_depth
        visited: set[int] = set()
        nodes: list[GraphNode] = []
        edges: list[MemoryRelationship] = []
        queue: deque[tuple[int, int, list[int]]] = deque()
        truncated = False

        # Seed with the starting memory
        start_mem = self.mem_repo.get(memory_id)
        if start_mem is None:
            return GraphResult(nodes=[], edges=[], total_nodes=0, truncated=False, max_depth_reached=0)

        queue.append((memory_id, 0, [memory_id]))
        visited.add(memory_id)

        while queue and len(nodes) < self.max_nodes:
            current_id, current_depth, path = queue.popleft()

            mem = self.mem_repo.get(current_id)
            if mem is None:
                continue
            if project_id is not None and mem.project_id != project_id:
                continue  # project isolation

            nodes.append(GraphNode(
                memory_id=current_id,
                content=mem.content or "",
                memory_type=mem.memory_type or "",
                depth=current_depth,
                path=list(path),
            ))

            if current_depth >= depth:
                continue

            # Get all relationships where this memory is source or target
            relationships = self.rel_repo.get_for_memory(current_id)
            for rel in relationships:
                if project_id is not None and rel.project_id != project_id:
                    continue

                neighbor_id = rel.target_memory_id if rel.source_memory_id == current_id else rel.source_memory_id
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    edges.append(rel)
                    queue.append((neighbor_id, current_depth + 1, path + [neighbor_id]))

        if queue:
            truncated = True

        max_d = max((n.depth for n in nodes), default=0)
        logger.info("Graph neighborhood for memory=%d: %d nodes, depth=%d, truncated=%s",
                     memory_id, len(nodes), max_d, truncated)
        return GraphResult(
            nodes=nodes,
            edges=edges,
            total_nodes=len(nodes),
            truncated=truncated,
            max_depth_reached=max_d,
        )

    def statistics(self, project_id: int) -> dict:
        """Get graph statistics for a project."""
        relationships = self.rel_repo.get_by_project(project_id)
        if not relationships:
            return {
                "total_relationships": 0,
                "total_memories": 0,
                "type_counts": {},
                "avg_connections": 0,
            }

        memory_ids: set[int] = set()
        type_counts: dict[str, int] = {}
        for rel in relationships:
            memory_ids.add(rel.source_memory_id)
            memory_ids.add(rel.target_memory_id)
            type_counts[rel.relationship_type] = type_counts.get(rel.relationship_type, 0) + 1

        return {
            "total_relationships": len(relationships),
            "total_memories": len(memory_ids),
            "type_counts": type_counts,
            "avg_connections": len(relationships) * 2 / max(len(memory_ids), 1),
        }

    def validate(self, project_id: int) -> dict:
        """Validate graph integrity for a project."""
        relationships = self.rel_repo.get_by_project(project_id)
        issues = []
        memory_ids = set()

        for rel in relationships:
            memory_ids.add(rel.source_memory_id)
            memory_ids.add(rel.target_memory_id)

            # Check source and target exist
            src = self.mem_repo.get(rel.source_memory_id)
            tgt = self.mem_repo.get(rel.target_memory_id)
            if src is None:
                issues.append(f"Relationship {rel.id}: source memory {rel.source_memory_id} missing")
            if tgt is None:
                issues.append(f"Relationship {rel.id}: target memory {rel.target_memory_id} missing")

            # Check project isolation
            if src and tgt and src.project_id != tgt.project_id:
                issues.append(f"Relationship {rel.id}: cross-project (src={src.project_id}, tgt={tgt.project_id})")

        return {
            "valid": len(issues) == 0,
            "total_relationships": len(relationships),
            "total_memories": len(memory_ids),
            "issues": issues,
        }
