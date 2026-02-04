"""
Tests for Ontology Diff Tool module.

Tests ontology comparison and merge functionality:
- Entity diff detection
- Property diff detection
- Relationship diff detection
- Business rule diff detection
- Changelog generation
- Three-way merge
"""

import pytest

from powerbi_ontology.ontology_diff import (
    OntologyDiff,
    OntologyMerge,
    DiffReport,
    Change,
    ChangeType,
    ElementType,
    diff_ontologies,
    merge_ontologies,
)
from powerbi_ontology.ontology_generator import (
    Ontology,
    OntologyEntity,
    OntologyProperty,
    OntologyRelationship,
    BusinessRule,
)


@pytest.fixture
def base_ontology():
    """Base ontology for testing."""
    return Ontology(
        name="Test_Ontology",
        version="1.0",
        source="test.pbix",
        entities=[
            OntologyEntity(
                name="Customer",
                description="Customer entity",
                entity_type="dimension",
                properties=[
                    OntologyProperty(name="Id", data_type="Integer", required=True),
                    OntologyProperty(name="Name", data_type="String", required=True),
                    OntologyProperty(name="Email", data_type="String"),
                ],
                constraints=[],
            ),
            OntologyEntity(
                name="Order",
                description="Order entity",
                entity_type="fact",
                properties=[
                    OntologyProperty(name="OrderId", data_type="Integer", required=True),
                    OntologyProperty(name="Amount", data_type="Decimal"),
                ],
                constraints=[],
            ),
        ],
        relationships=[
            OntologyRelationship(
                from_entity="Order",
                to_entity="Customer",
                from_property="CustomerId",
                to_property="Id",
                relationship_type="belongs_to",
                cardinality="many-to-one",
            ),
        ],
        business_rules=[
            BusinessRule(
                name="HighValue",
                entity="Order",
                condition="Amount > 1000",
                action="Flag",
                classification="high",
            ),
        ],
        metadata={"author": "test"},
    )


@pytest.fixture
def modified_ontology(base_ontology):
    """Modified ontology with some changes."""
    return Ontology(
        name="Test_Ontology",
        version="1.1",
        source="test.pbix",
        entities=[
            OntologyEntity(
                name="Customer",
                description="Updated customer entity",  # Modified
                entity_type="dimension",
                properties=[
                    OntologyProperty(name="Id", data_type="Integer", required=True),
                    OntologyProperty(name="Name", data_type="String", required=True),
                    OntologyProperty(name="Email", data_type="String"),
                    OntologyProperty(name="Phone", data_type="String"),  # Added
                ],
                constraints=[],
            ),
            # Order entity removed
            OntologyEntity(
                name="Product",  # Added
                description="Product entity",
                entity_type="dimension",
                properties=[
                    OntologyProperty(name="ProductId", data_type="Integer", required=True),
                    OntologyProperty(name="Name", data_type="String"),
                ],
                constraints=[],
            ),
        ],
        relationships=[
            # Order→Customer removed
        ],
        business_rules=[
            BusinessRule(
                name="HighValue",
                entity="Order",
                condition="Amount > 5000",  # Modified threshold
                action="Flag",
                classification="high",
            ),
        ],
        metadata={"author": "test", "version_note": "Updated"},
    )


class TestOntologyDiff:
    """Tests for OntologyDiff class."""

    def test_diff_no_changes(self, base_ontology):
        """Test diff with identical ontologies."""
        diff = OntologyDiff(base_ontology, base_ontology)
        report = diff.diff()

        assert not report.has_changes()
        assert report.summary["total_changes"] == 0

    def test_diff_detects_added_entity(self, base_ontology, modified_ontology):
        """Test detection of added entities."""
        diff = OntologyDiff(base_ontology, modified_ontology)
        report = diff.diff()

        added = [c for c in report.changes if c.change_type == ChangeType.ADDED and c.element_type == ElementType.ENTITY]
        assert any(c.element_name == "Product" for c in added)

    def test_diff_detects_removed_entity(self, base_ontology, modified_ontology):
        """Test detection of removed entities."""
        diff = OntologyDiff(base_ontology, modified_ontology)
        report = diff.diff()

        removed = [c for c in report.changes if c.change_type == ChangeType.REMOVED and c.element_type == ElementType.ENTITY]
        assert any(c.element_name == "Order" for c in removed)

    def test_diff_detects_modified_entity(self, base_ontology, modified_ontology):
        """Test detection of modified entity description."""
        diff = OntologyDiff(base_ontology, modified_ontology)
        report = diff.diff()

        modified = [c for c in report.changes if c.change_type == ChangeType.MODIFIED and "Customer" in c.path]
        assert len(modified) > 0

    def test_diff_detects_added_property(self, base_ontology, modified_ontology):
        """Test detection of added properties."""
        diff = OntologyDiff(base_ontology, modified_ontology)
        report = diff.diff()

        added = [c for c in report.changes if c.change_type == ChangeType.ADDED and c.element_type == ElementType.PROPERTY]
        assert any("Phone" in c.path for c in added)

    def test_diff_detects_removed_relationship(self, base_ontology, modified_ontology):
        """Test detection of removed relationships."""
        diff = OntologyDiff(base_ontology, modified_ontology)
        report = diff.diff()

        removed = [c for c in report.changes if c.change_type == ChangeType.REMOVED and c.element_type == ElementType.RELATIONSHIP]
        assert len(removed) > 0

    def test_diff_detects_modified_rule(self, base_ontology, modified_ontology):
        """Test detection of modified business rules."""
        diff = OntologyDiff(base_ontology, modified_ontology)
        report = diff.diff()

        modified = [c for c in report.changes if c.change_type == ChangeType.MODIFIED and c.element_type == ElementType.RULE]
        assert any("HighValue" in c.element_name for c in modified)

    def test_diff_detects_added_metadata(self, base_ontology, modified_ontology):
        """Test detection of added metadata."""
        diff = OntologyDiff(base_ontology, modified_ontology)
        report = diff.diff()

        added = [c for c in report.changes if c.change_type == ChangeType.ADDED and c.element_type == ElementType.METADATA]
        assert any("version_note" in c.element_name for c in added)


class TestDiffReport:
    """Tests for DiffReport class."""

    def test_add_change(self):
        """Test adding changes to report."""
        report = DiffReport(
            source_name="v1",
            target_name="v2",
            source_version="1.0",
            target_version="2.0",
        )

        change = Change(
            change_type=ChangeType.ADDED,
            element_type=ElementType.ENTITY,
            element_name="Test",
            path="Test",
            new_value="value",
        )

        report.add_change(change)
        assert len(report.changes) == 1

    def test_generate_summary(self, base_ontology, modified_ontology):
        """Test summary generation."""
        diff = OntologyDiff(base_ontology, modified_ontology)
        report = diff.diff()
        report.generate_summary()

        assert "total_changes" in report.summary
        assert "added" in report.summary
        assert "removed" in report.summary
        assert "modified" in report.summary

    def test_to_dict(self, base_ontology, modified_ontology):
        """Test conversion to dictionary."""
        diff = OntologyDiff(base_ontology, modified_ontology)
        report = diff.diff()
        result = report.to_dict()

        assert "source" in result
        assert "target" in result
        assert "summary" in result
        assert "changes" in result

    def test_to_changelog(self, base_ontology, modified_ontology):
        """Test changelog generation."""
        diff = OntologyDiff(base_ontology, modified_ontology)
        report = diff.diff()
        changelog = report.to_changelog()

        assert "# Changelog" in changelog
        assert "## Summary" in changelog
        assert "Added" in changelog or "Removed" in changelog or "Modified" in changelog

    def test_has_changes(self, base_ontology, modified_ontology):
        """Test has_changes method."""
        diff = OntologyDiff(base_ontology, modified_ontology)
        report = diff.diff()

        assert report.has_changes()


class TestPropertyDiff:
    """Tests for property-level diff detection."""

    def test_type_change_detected(self):
        """Test detection of property type changes."""
        source = Ontology(
            name="Test",
            version="1.0",
            source="test",
            entities=[
                OntologyEntity(
                    name="Entity",
                    description="",
                    entity_type="standard",
                    properties=[
                        OntologyProperty(name="Field", data_type="Integer"),
                    ],
                    constraints=[],
                ),
            ],
            relationships=[],
            business_rules=[],
        )

        target = Ontology(
            name="Test",
            version="1.1",
            source="test",
            entities=[
                OntologyEntity(
                    name="Entity",
                    description="",
                    entity_type="standard",
                    properties=[
                        OntologyProperty(name="Field", data_type="String"),  # Changed
                    ],
                    constraints=[],
                ),
            ],
            relationships=[],
            business_rules=[],
        )

        diff = OntologyDiff(source, target)
        report = diff.diff()

        type_changes = [c for c in report.changes if "data_type" in c.path]
        assert len(type_changes) == 1
        assert type_changes[0].old_value == "Integer"
        assert type_changes[0].new_value == "String"

    def test_required_flag_change_detected(self):
        """Test detection of required flag changes."""
        source = Ontology(
            name="Test",
            version="1.0",
            source="test",
            entities=[
                OntologyEntity(
                    name="Entity",
                    description="",
                    entity_type="standard",
                    properties=[
                        OntologyProperty(name="Field", data_type="String", required=False),
                    ],
                    constraints=[],
                ),
            ],
            relationships=[],
            business_rules=[],
        )

        target = Ontology(
            name="Test",
            version="1.1",
            source="test",
            entities=[
                OntologyEntity(
                    name="Entity",
                    description="",
                    entity_type="standard",
                    properties=[
                        OntologyProperty(name="Field", data_type="String", required=True),  # Changed
                    ],
                    constraints=[],
                ),
            ],
            relationships=[],
            business_rules=[],
        )

        diff = OntologyDiff(source, target)
        report = diff.diff()

        required_changes = [c for c in report.changes if "required" in c.path]
        assert len(required_changes) == 1


class TestRelationshipDiff:
    """Tests for relationship diff detection."""

    def test_cardinality_change_detected(self):
        """Test detection of cardinality changes."""
        source = Ontology(
            name="Test",
            version="1.0",
            source="test",
            entities=[],
            relationships=[
                OntologyRelationship(
                    from_entity="A",
                    to_entity="B",
                    from_property="",
                    to_property="",
                    relationship_type="related",
                    cardinality="one-to-many",
                ),
            ],
            business_rules=[],
        )

        target = Ontology(
            name="Test",
            version="1.1",
            source="test",
            entities=[],
            relationships=[
                OntologyRelationship(
                    from_entity="A",
                    to_entity="B",
                    from_property="",
                    to_property="",
                    relationship_type="related",
                    cardinality="many-to-many",  # Changed
                ),
            ],
            business_rules=[],
        )

        diff = OntologyDiff(source, target)
        report = diff.diff()

        cardinality_changes = [c for c in report.changes if "cardinality" in c.path]
        assert len(cardinality_changes) == 1


class TestOntologyMerge:
    """Tests for OntologyMerge class."""

    def test_merge_non_conflicting(self, base_ontology):
        """Test merge without conflicts."""
        # Ours: add Phone property
        ours = Ontology(
            name=base_ontology.name,
            version="1.1",
            source=base_ontology.source,
            entities=[
                OntologyEntity(
                    name="Customer",
                    description="Customer entity",
                    entity_type="dimension",
                    properties=[
                        OntologyProperty(name="Id", data_type="Integer", required=True),
                        OntologyProperty(name="Name", data_type="String", required=True),
                        OntologyProperty(name="Email", data_type="String"),
                        OntologyProperty(name="Phone", data_type="String"),  # Added
                    ],
                    constraints=[],
                ),
                base_ontology.entities[1],  # Order unchanged
            ],
            relationships=base_ontology.relationships,
            business_rules=base_ontology.business_rules,
            metadata=base_ontology.metadata,
        )

        # Theirs: add Address property
        theirs = Ontology(
            name=base_ontology.name,
            version="1.1",
            source=base_ontology.source,
            entities=[
                OntologyEntity(
                    name="Customer",
                    description="Customer entity",
                    entity_type="dimension",
                    properties=[
                        OntologyProperty(name="Id", data_type="Integer", required=True),
                        OntologyProperty(name="Name", data_type="String", required=True),
                        OntologyProperty(name="Email", data_type="String"),
                        OntologyProperty(name="Address", data_type="String"),  # Added
                    ],
                    constraints=[],
                ),
                base_ontology.entities[1],  # Order unchanged
            ],
            relationships=base_ontology.relationships,
            business_rules=base_ontology.business_rules,
            metadata=base_ontology.metadata,
        )

        merger = OntologyMerge(base_ontology, ours, theirs)
        merged, conflicts = merger.merge()

        assert merged is not None
        assert "1.2" in merged.version or "1.1.1" in merged.version

    def test_merge_with_new_entity(self, base_ontology):
        """Test merge when one side adds new entity."""
        theirs = Ontology(
            name=base_ontology.name,
            version="1.1",
            source=base_ontology.source,
            entities=[
                *base_ontology.entities,
                OntologyEntity(
                    name="Product",
                    description="Product entity",
                    entity_type="dimension",
                    properties=[
                        OntologyProperty(name="ProductId", data_type="Integer", required=True),
                    ],
                    constraints=[],
                ),
            ],
            relationships=base_ontology.relationships,
            business_rules=base_ontology.business_rules,
        )

        merged, conflicts = merge_ontologies(base_ontology, base_ontology, theirs)

        entity_names = [e.name for e in merged.entities]
        assert "Product" in entity_names


class TestChange:
    """Tests for Change dataclass."""

    def test_to_dict(self):
        """Test Change.to_dict()."""
        change = Change(
            change_type=ChangeType.MODIFIED,
            element_type=ElementType.PROPERTY,
            element_name="Field",
            path="Entity.Field",
            old_value="Integer",
            new_value="String",
            details="Type changed",
        )

        result = change.to_dict()

        assert result["change_type"] == "modified"
        assert result["element_type"] == "property"
        assert result["element_name"] == "Field"
        assert result["old_value"] == "Integer"
        assert result["new_value"] == "String"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_diff_ontologies(self, base_ontology, modified_ontology):
        """Test diff_ontologies convenience function."""
        report = diff_ontologies(base_ontology, modified_ontology)

        assert isinstance(report, DiffReport)
        assert report.has_changes()

    def test_merge_ontologies(self, base_ontology):
        """Test merge_ontologies convenience function."""
        merged, conflicts = merge_ontologies(
            base_ontology,
            base_ontology,
            base_ontology,
        )

        assert isinstance(merged, Ontology)
        assert isinstance(conflicts, list)
