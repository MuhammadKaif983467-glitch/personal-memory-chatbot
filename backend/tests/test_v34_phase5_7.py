"""V3.4 Phases 5-7: Memory intelligence, multi-hop, and graph API tests."""

import pytest
from unittest.mock import MagicMock
from app.services.memory_graph import MemoryGraphService, GraphNode, GraphResult


class TestMemoryGraphService:
    def test_neighborhood_empty_memory(self, app, db):
        """Non-existent memory returns empty graph."""
        graph = MemoryGraphService(db)
        result = graph.neighborhood(99999)
        assert result.total_nodes == 0
        assert result.nodes == []

    def test_neighborhood_isolated_memory(self, app, db):
        """Memory with no relationships returns single node."""
        from app.database.repositories import PersonRepository, MemoryRepository
        person = PersonRepository(db).create("GraphTest", project_id=1)
        mem_repo = MemoryRepository(db)
        mem = mem_repo.create(person_id=person.id, content="isolated memory", memory_type="FACT", project_id=1)
        db.commit()

        graph = MemoryGraphService(db)
        result = graph.neighborhood(mem.id)
        assert result.total_nodes == 1
        assert result.nodes[0].memory_id == mem.id
        assert result.max_depth_reached == 0

    def test_neighborhood_with_relationship(self, app, db):
        """Memory with one relationship returns two nodes."""
        from app.database.repositories import PersonRepository, MemoryRepository, MemoryRelationshipRepository
        person = PersonRepository(db).create("GraphRel", project_id=1)
        mem_repo = MemoryRepository(db)
        m1 = mem_repo.create(person_id=person.id, content="memory one", memory_type="FACT", project_id=1)
        m2 = mem_repo.create(person_id=person.id, content="memory two", memory_type="FACT", project_id=1)
        db.commit()

        rel_repo = MemoryRelationshipRepository(db)
        rel_repo.create(
            project_id=1, source_memory_id=m1.id, target_memory_id=m2.id,
            relationship_type="supports",
        )
        db.commit()

        graph = MemoryGraphService(db)
        result = graph.neighborhood(m1.id)
        assert result.total_nodes == 2
        assert len(result.edges) == 1

    def test_neighborhood_respects_max_depth(self, app, db):
        """Deeper chains are truncated at max_depth."""
        from app.database.repositories import PersonRepository, MemoryRepository, MemoryRelationshipRepository
        person = PersonRepository(db).create("GraphDepth", project_id=1)
        mem_repo = MemoryRepository(db)
        m1 = mem_repo.create(person_id=person.id, content="m1", memory_type="FACT", project_id=1)
        m2 = mem_repo.create(person_id=person.id, content="m2", memory_type="FACT", project_id=1)
        m3 = mem_repo.create(person_id=person.id, content="m3", memory_type="FACT", project_id=1)
        db.commit()

        rel_repo = MemoryRelationshipRepository(db)
        rel_repo.create(project_id=1, source_memory_id=m1.id, target_memory_id=m2.id, relationship_type="related_to")
        rel_repo.create(project_id=1, source_memory_id=m2.id, target_memory_id=m3.id, relationship_type="related_to")
        db.commit()

        graph = MemoryGraphService(db, max_depth=1)
        result = graph.neighborhood(m1.id)
        # At depth 1, we should see m1 and m2 but not m3
        node_ids = {n.memory_id for n in result.nodes}
        assert m1.id in node_ids
        assert m2.id in node_ids
        assert m3.id not in node_ids

    def test_neighborhood_respects_max_nodes(self, app, db):
        """Node count is bounded by max_nodes."""
        from app.database.repositories import PersonRepository, MemoryRepository
        person = PersonRepository(db).create("GraphNode", project_id=1)
        mem_repo = MemoryRepository(db)
        mems = [mem_repo.create(person_id=person.id, content=f"mem{i}", memory_type="FACT", project_id=1) for i in range(10)]
        db.commit()

        graph = MemoryGraphService(db, max_depth=3, max_nodes=5)
        result = graph.neighborhood(mems[0].id)
        assert result.total_nodes <= 5

    def test_cycle_detection(self, app, db):
        """Cycles in the graph don't cause infinite loops."""
        from app.database.repositories import PersonRepository, MemoryRepository, MemoryRelationshipRepository
        person = PersonRepository(db).create("GraphCycle", project_id=1)
        mem_repo = MemoryRepository(db)
        m1 = mem_repo.create(person_id=person.id, content="c1", memory_type="FACT", project_id=1)
        m2 = mem_repo.create(person_id=person.id, content="c2", memory_type="FACT", project_id=1)
        db.commit()

        rel_repo = MemoryRelationshipRepository(db)
        rel_repo.create(project_id=1, source_memory_id=m1.id, target_memory_id=m2.id, relationship_type="related_to")
        rel_repo.create(project_id=1, source_memory_id=m2.id, target_memory_id=m1.id, relationship_type="related_to")
        db.commit()

        graph = MemoryGraphService(db, max_depth=3)
        result = graph.neighborhood(m1.id)
        # Should terminate despite cycle
        assert result.total_nodes == 2

    def test_statistics(self, app, db):
        """Graph statistics return correct counts."""
        from app.database.repositories import PersonRepository, MemoryRepository, MemoryRelationshipRepository
        person = PersonRepository(db).create("GraphStats", project_id=1)
        mem_repo = MemoryRepository(db)
        m1 = mem_repo.create(person_id=person.id, content="s1", memory_type="FACT", project_id=1)
        m2 = mem_repo.create(person_id=person.id, content="s2", memory_type="FACT", project_id=1)
        db.commit()

        rel_repo = MemoryRelationshipRepository(db)
        rel_repo.create(project_id=1, source_memory_id=m1.id, target_memory_id=m2.id, relationship_type="supports")
        db.commit()

        graph = MemoryGraphService(db)
        stats = graph.statistics(1)
        assert stats["total_relationships"] == 1
        assert stats["total_memories"] == 2
        assert stats["type_counts"]["supports"] == 1

    def test_validate_clean_project(self, app, db):
        """Validation passes for clean project."""
        from app.database.repositories import PersonRepository, MemoryRepository
        person = PersonRepository(db).create("GraphValid", project_id=1)
        mem_repo = MemoryRepository(db)
        mem_repo.create(person_id=person.id, content="v1", memory_type="FACT", project_id=1)
        db.commit()

        graph = MemoryGraphService(db)
        result = graph.validate(1)
        assert result["valid"] is True

    def test_project_isolation(self, app, db):
        """Graph traversal respects project boundaries when querying."""
        from app.database.repositories import PersonRepository, MemoryRepository, MemoryRelationshipRepository
        person_repo = PersonRepository(db)
        p1 = person_repo.create("Iso1", project_id=1)
        mem_repo = MemoryRepository(db)
        m1 = mem_repo.create(person_id=p1.id, content="proj1mem", memory_type="FACT", project_id=1)
        m2 = mem_repo.create(person_id=p1.id, content="proj1mem2", memory_type="FACT", project_id=1)
        db.commit()

        rel_repo = MemoryRelationshipRepository(db)
        rel_repo.create(project_id=1, source_memory_id=m1.id, target_memory_id=m2.id, relationship_type="related_to")
        db.commit()

        graph = MemoryGraphService(db)
        # Query with wrong project_id should exclude the nodes
        result = graph.neighborhood(m1.id, project_id=999)
        node_ids = {n.memory_id for n in result.nodes}
        assert m1.id not in node_ids
        assert m2.id not in node_ids
