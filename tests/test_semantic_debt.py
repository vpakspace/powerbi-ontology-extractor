"""
Tests for Semantic Debt Analysis module.

Tests multi-dashboard conflict detection:
- Entity structure conflicts
- Property type conflicts
- Relationship conflicts
- Business rule conflicts
"""

import pytest

from powerbi_ontology.semantic_debt import (
    SemanticDebtAnalyzer,
    SemanticDebtReport,
    SemanticConflict,
    ConflictType,
    ConflictSeverity,
    analyze_ontologies,
)
from powerbi_ontology.ontology_generator import (
    Ontology,
    OntologyEntity,
    OntologyProperty,
    OntologyRelationship,
    BusinessRule,
)


@pytest.fixture
def sales_ontology():
    """Sales dashboard ontology."""
    return Ontology(
        name="Sales_Dashboard",
        version="1.0",
        source="Sales.pbix",
        entities=[
            OntologyEntity(
                name="Customer",
                description="Customer from Sales",
                entity_type="dimension",
                properties=[
                    OntologyProperty(name="CustomerId", data_type="Integer", required=True),
                    OntologyProperty(name="Name", data_type="String", required=True),
                    OntologyProperty(name="Email", data_type="String"),
                    OntologyProperty(name="Region", data_type="String"),
                ],
                constraints=[],
            ),
            OntologyEntity(
                name="Order",
                description="Sales orders",
                entity_type="fact",
                properties=[
                    OntologyProperty(name="OrderId", data_type="Integer", required=True),
                    OntologyProperty(name="Amount", data_type="Decimal"),
                    OntologyProperty(name="OrderDate", data_type="DateTime"),
                ],
                constraints=[],
            ),
        ],
        relationships=[
            OntologyRelationship(
                from_entity="Order",
                to_entity="Customer",
                from_property="CustomerId",
                to_property="CustomerId",
                relationship_type="belongs_to",
                cardinality="many-to-one",
            ),
        ],
        business_rules=[
            BusinessRule(
                name="HighValueOrder",
                entity="Order",
                condition="Amount > 10000",
                action="RequireApproval",
                classification="high",
            ),
        ],
    )


@pytest.fixture
def finance_ontology():
    """Finance dashboard ontology with some conflicts."""
    return Ontology(
        name="Finance_Dashboard",
        version="1.0",
        source="Finance.pbix",
        entities=[
            OntologyEntity(
                name="Customer",
                description="Customer from Finance",
                entity_type="dimension",
                properties=[
                    OntologyProperty(name="CustomerId", data_type="String", required=True),  # TYPE CONFLICT: String vs Integer
                    OntologyProperty(name="Name", data_type="String", required=True),
                    OntologyProperty(name="CreditLimit", data_type="Decimal"),  # Different property
                ],
                constraints=[],
            ),
            OntologyEntity(
                name="Invoice",
                description="Invoices",
                entity_type="fact",
                properties=[
                    OntologyProperty(name="InvoiceId", data_type="Integer", required=True),
                    OntologyProperty(name="Amount", data_type="Decimal"),
                ],
                constraints=[],
            ),
        ],
        relationships=[
            OntologyRelationship(
                from_entity="Invoice",
                to_entity="Customer",
                from_property="CustomerId",
                to_property="CustomerId",
                relationship_type="belongs_to",
                cardinality="one-to-many",  # Different cardinality
            ),
        ],
        business_rules=[
            BusinessRule(
                name="HighValueOrder",  # Same name, different condition
                entity="Invoice",
                condition="Amount > 50000",  # Different threshold
                action="RequireApproval",
                classification="high",
            ),
        ],
    )


@pytest.fixture
def marketing_ontology():
    """Marketing dashboard ontology (no major conflicts)."""
    return Ontology(
        name="Marketing_Dashboard",
        version="1.0",
        source="Marketing.pbix",
        entities=[
            OntologyEntity(
                name="Campaign",
                description="Marketing campaigns",
                entity_type="fact",
                properties=[
                    OntologyProperty(name="CampaignId", data_type="Integer", required=True),
                    OntologyProperty(name="Name", data_type="String"),
                    OntologyProperty(name="Budget", data_type="Decimal"),
                ],
                constraints=[],
            ),
        ],
        relationships=[],
        business_rules=[],
    )


class TestSemanticDebtAnalyzer:
    """Tests for SemanticDebtAnalyzer class."""

    def test_init(self):
        """Test analyzer initialization."""
        analyzer = SemanticDebtAnalyzer()
        assert analyzer.similarity_threshold == 0.8
        assert len(analyzer.ontologies) == 0

    def test_add_ontology(self, sales_ontology):
        """Test adding ontology."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("sales", sales_ontology)

        assert "sales" in analyzer.ontologies
        assert analyzer.ontologies["sales"] == sales_ontology

    def test_analyze_single_ontology(self, sales_ontology):
        """Test that single ontology returns empty report."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("sales", sales_ontology)

        report = analyzer.analyze()

        assert len(report.conflicts) == 0
        assert "sales" in report.ontologies_analyzed

    def test_analyze_two_ontologies(self, sales_ontology, finance_ontology):
        """Test analyzing two ontologies with conflicts."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("Sales.pbix", sales_ontology)
        analyzer.add_ontology("Finance.pbix", finance_ontology)

        report = analyzer.analyze()

        assert len(report.conflicts) > 0
        assert len(report.ontologies_analyzed) == 2


class TestEntityConflicts:
    """Tests for entity structure conflict detection."""

    def test_entity_structure_conflict(self, sales_ontology, finance_ontology):
        """Test detection of entity structure differences."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("Sales.pbix", sales_ontology)
        analyzer.add_ontology("Finance.pbix", finance_ontology)

        report = analyzer.analyze()

        # Customer entity has different properties
        entity_conflicts = [
            c for c in report.conflicts
            if c.conflict_type == ConflictType.ENTITY_CONFLICT
        ]

        assert len(entity_conflicts) > 0

        customer_conflict = next(
            (c for c in entity_conflicts if c.name == "Customer"),
            None
        )
        assert customer_conflict is not None

    def test_no_entity_conflict_for_unique_entities(self, sales_ontology, marketing_ontology):
        """Test no conflict for unique entities."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("Sales.pbix", sales_ontology)
        analyzer.add_ontology("Marketing.pbix", marketing_ontology)

        report = analyzer.analyze()

        # No overlapping entities
        entity_conflicts = [
            c for c in report.conflicts
            if c.conflict_type == ConflictType.ENTITY_CONFLICT
        ]

        assert len(entity_conflicts) == 0


class TestPropertyTypeConflicts:
    """Tests for property type conflict detection."""

    def test_type_conflict_detected(self, sales_ontology, finance_ontology):
        """Test detection of property type conflicts."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("Sales.pbix", sales_ontology)
        analyzer.add_ontology("Finance.pbix", finance_ontology)

        report = analyzer.analyze()

        type_conflicts = [
            c for c in report.conflicts
            if c.conflict_type == ConflictType.TYPE_CONFLICT
        ]

        # CustomerId is Integer in Sales, String in Finance
        assert len(type_conflicts) > 0

        customer_id_conflict = next(
            (c for c in type_conflicts if "CustomerId" in c.name),
            None
        )
        assert customer_id_conflict is not None
        assert customer_id_conflict.severity == ConflictSeverity.CRITICAL

    def test_type_conflict_severity_is_critical(self, sales_ontology, finance_ontology):
        """Test that type conflicts are always critical."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("Sales.pbix", sales_ontology)
        analyzer.add_ontology("Finance.pbix", finance_ontology)

        report = analyzer.analyze()

        type_conflicts = [
            c for c in report.conflicts
            if c.conflict_type == ConflictType.TYPE_CONFLICT
        ]

        for conflict in type_conflicts:
            assert conflict.severity == ConflictSeverity.CRITICAL


class TestBusinessRuleConflicts:
    """Tests for business rule conflict detection."""

    def test_rule_conflict_detected(self, sales_ontology, finance_ontology):
        """Test detection of business rule conflicts."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("Sales.pbix", sales_ontology)
        analyzer.add_ontology("Finance.pbix", finance_ontology)

        report = analyzer.analyze()

        rule_conflicts = [
            c for c in report.conflicts
            if c.conflict_type == ConflictType.RULE_CONFLICT
        ]

        # HighValueOrder has different conditions
        assert len(rule_conflicts) > 0

        hvr_conflict = next(
            (c for c in rule_conflicts if c.name == "HighValueOrder"),
            None
        )
        assert hvr_conflict is not None


class TestSemanticDebtReport:
    """Tests for SemanticDebtReport class."""

    def test_add_conflict(self):
        """Test adding conflict to report."""
        report = SemanticDebtReport(ontologies_analyzed=["test1", "test2"])

        conflict = SemanticConflict(
            conflict_type=ConflictType.TYPE_CONFLICT,
            severity=ConflictSeverity.CRITICAL,
            name="Test.Property",
            sources=["test1", "test2"],
            details={"test1": "Integer", "test2": "String"},
            description="Test conflict",
        )

        report.add_conflict(conflict)

        assert len(report.conflicts) == 1

    def test_generate_summary(self, sales_ontology, finance_ontology):
        """Test summary generation."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("Sales.pbix", sales_ontology)
        analyzer.add_ontology("Finance.pbix", finance_ontology)

        report = analyzer.analyze()
        report.generate_summary()

        assert "total_conflicts" in report.summary
        assert report.summary["total_conflicts"] == len(report.conflicts)
        assert "critical" in report.summary
        assert "warning" in report.summary
        assert "info" in report.summary

    def test_to_dict(self, sales_ontology, finance_ontology):
        """Test conversion to dictionary."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("Sales.pbix", sales_ontology)
        analyzer.add_ontology("Finance.pbix", finance_ontology)

        report = analyzer.analyze()
        result = report.to_dict()

        assert "ontologies_analyzed" in result
        assert "summary" in result
        assert "conflicts" in result
        assert "recommendations" in result

    def test_to_markdown(self, sales_ontology, finance_ontology):
        """Test markdown report generation."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("Sales.pbix", sales_ontology)
        analyzer.add_ontology("Finance.pbix", finance_ontology)

        report = analyzer.analyze()
        markdown = report.to_markdown()

        assert "# Semantic Debt Analysis Report" in markdown
        assert "## Summary" in markdown
        assert "Critical" in markdown or "Warning" in markdown


class TestRecommendations:
    """Tests for recommendation generation."""

    def test_recommendations_generated(self, sales_ontology, finance_ontology):
        """Test that recommendations are generated."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("Sales.pbix", sales_ontology)
        analyzer.add_ontology("Finance.pbix", finance_ontology)

        report = analyzer.analyze()

        assert len(report.recommendations) > 0

    def test_no_conflicts_recommendation(self, sales_ontology, marketing_ontology):
        """Test recommendation when no conflicts."""
        analyzer = SemanticDebtAnalyzer()
        analyzer.add_ontology("Sales.pbix", sales_ontology)
        analyzer.add_ontology("Marketing.pbix", marketing_ontology)

        report = analyzer.analyze()

        # Should have either no recommendations or positive message
        if report.recommendations:
            assert any("No semantic conflicts" in r or "Good" in r for r in report.recommendations)


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_analyze_ontologies_function(self, sales_ontology, finance_ontology):
        """Test analyze_ontologies convenience function."""
        ontologies = {
            "Sales.pbix": sales_ontology,
            "Finance.pbix": finance_ontology,
        }

        report = analyze_ontologies(ontologies)

        assert isinstance(report, SemanticDebtReport)
        assert len(report.conflicts) > 0


class TestConflictSerialization:
    """Tests for conflict serialization."""

    def test_conflict_to_dict(self):
        """Test SemanticConflict.to_dict()."""
        conflict = SemanticConflict(
            conflict_type=ConflictType.TYPE_CONFLICT,
            severity=ConflictSeverity.CRITICAL,
            name="Test.Property",
            sources=["file1.pbix", "file2.pbix"],
            details={"file1.pbix": "Integer", "file2.pbix": "String"},
            description="Type mismatch",
            recommendation="Standardize type",
        )

        result = conflict.to_dict()

        assert result["conflict_type"] == "type_conflict"
        assert result["severity"] == "critical"
        assert result["name"] == "Test.Property"
        assert len(result["sources"]) == 2
        assert "description" in result
        assert "recommendation" in result
