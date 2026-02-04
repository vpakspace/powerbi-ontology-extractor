"""
Tests for OWLExporter.

Tests the enhanced OWL exporter with:
- Action rules (requiresRole, appliesTo, allowsAction) for OntoGuard
- Property constraints (required, range, enum)
- RLS rules as OWL restrictions
"""

import pytest
from rdflib import Graph
from rdflib.namespace import RDF, RDFS, OWL, XSD

from powerbi_ontology.export.owl import OWLExporter
from powerbi_ontology.ontology_generator import (
    Ontology,
    OntologyEntity,
    OntologyProperty,
    BusinessRule,
    Constraint,
)


class TestOWLExporter:
    """Test OWLExporter class."""

    def test_init(self, sample_ontology):
        """Test exporter initialization."""
        exporter = OWLExporter(sample_ontology)
        assert exporter.ontology == sample_ontology
        assert exporter.graph is not None

    def test_init_custom_base_uri(self, sample_ontology):
        """Test exporter with custom base URI."""
        custom_uri = "http://mycompany.com/ontologies/test#"
        exporter = OWLExporter(sample_ontology, base_uri=custom_uri)
        assert exporter.base_uri == custom_uri

    def test_init_custom_roles(self, sample_ontology):
        """Test exporter with custom default roles."""
        custom_roles = ["SuperAdmin", "Manager", "ReadOnlyUser"]
        exporter = OWLExporter(sample_ontology, default_roles=custom_roles)
        assert exporter.default_roles == custom_roles

    def test_init_disable_action_rules(self, sample_ontology):
        """Test exporter with action rules disabled."""
        exporter = OWLExporter(sample_ontology, include_action_rules=False)
        owl_xml = exporter.export(format="xml")

        # Should not contain action-related elements
        assert "ReadAction" not in owl_xml
        assert "requiresRole" not in owl_xml

    def test_export_xml(self, sample_ontology):
        """Test exporting to OWL XML format."""
        exporter = OWLExporter(sample_ontology)
        owl_xml = exporter.export(format="xml")

        assert isinstance(owl_xml, str)
        assert len(owl_xml) > 0
        # May contain RDF/OWL elements
        assert "rdf" in owl_xml.lower() or "owl" in owl_xml.lower()

    def test_export_turtle(self, sample_ontology):
        """Test exporting to Turtle format."""
        exporter = OWLExporter(sample_ontology)
        owl_turtle = exporter.export(format="turtle")

        assert isinstance(owl_turtle, str)
        assert len(owl_turtle) > 0

    def test_add_entity(self, sample_ontology):
        """Test adding entity as OWL class."""
        exporter = OWLExporter(sample_ontology)
        entity = sample_ontology.entities[0]

        exporter._add_entity(entity)

        # Graph should have been modified
        assert exporter.graph is not None
        entity_uri = exporter.ont[exporter._safe_name(entity.name)]
        assert (entity_uri, RDF.type, OWL.Class) in exporter.graph

    def test_add_relationship(self, sample_ontology):
        """Test adding relationship as OWL object property."""
        exporter = OWLExporter(sample_ontology)
        if sample_ontology.relationships:
            rel = sample_ontology.relationships[0]

            exporter._add_relationship(rel)

            # Graph should have been modified
            assert exporter.graph is not None

    def test_map_to_xsd(self, sample_ontology):
        """Test mapping ontology types to XSD types."""
        exporter = OWLExporter(sample_ontology)

        assert exporter._map_to_xsd("String") == XSD.string
        assert exporter._map_to_xsd("Integer") == XSD.integer
        assert exporter._map_to_xsd("Decimal") == XSD.decimal
        assert exporter._map_to_xsd("DateTime") == XSD.dateTime
        assert exporter._map_to_xsd("Boolean") == XSD.boolean
        assert exporter._map_to_xsd("Float") == XSD.float
        assert exporter._map_to_xsd("Unknown") == XSD.string  # Default

    def test_save(self, sample_ontology, temp_dir):
        """Test saving OWL export to file."""
        exporter = OWLExporter(sample_ontology)
        output_path = temp_dir / "test_ontology.owl"

        exporter.save(str(output_path), format="xml")

        assert output_path.exists()
        content = output_path.read_text()
        assert len(content) > 0

    def test_safe_name(self, sample_ontology):
        """Test URI name sanitization."""
        exporter = OWLExporter(sample_ontology)

        assert exporter._safe_name("My Entity") == "My_Entity"
        assert exporter._safe_name("Entity-Name") == "Entity_Name"
        assert exporter._safe_name("Entity.Name") == "Entity_Name"
        assert exporter._safe_name("") == "unnamed"


class TestOWLExporterActionRules:
    """Test action rules generation for OntoGuard compatibility."""

    def test_base_classes_created(self, sample_ontology):
        """Test that User and Action base classes are created."""
        exporter = OWLExporter(sample_ontology)
        exporter.export()

        # Check User class
        user_uri = exporter.ont.User
        assert (user_uri, RDF.type, OWL.Class) in exporter.graph

        # Check Action class
        action_uri = exporter.ont.Action
        assert (action_uri, RDF.type, OWL.Class) in exporter.graph

    def test_action_subclasses_created(self, sample_ontology):
        """Test that action subclasses are created."""
        exporter = OWLExporter(sample_ontology)
        exporter.export()

        action_uri = exporter.ont.Action

        for action_type in ["ReadAction", "WriteAction", "DeleteAction", "ExecuteAction"]:
            action_class = exporter.ont[action_type]
            assert (action_class, RDF.type, OWL.Class) in exporter.graph
            assert (action_class, RDFS.subClassOf, action_uri) in exporter.graph

    def test_ontoguard_properties_created(self, sample_ontology):
        """Test that OntoGuard properties are created."""
        exporter = OWLExporter(sample_ontology)
        exporter.export()

        # Check requiresRole property
        requires_role = exporter.ont.requiresRole
        assert (requires_role, RDF.type, OWL.ObjectProperty) in exporter.graph

        # Check appliesTo property
        applies_to = exporter.ont.appliesTo
        assert (applies_to, RDF.type, OWL.ObjectProperty) in exporter.graph

        # Check allowsAction property
        allows_action = exporter.ont.allowsAction
        assert (allows_action, RDF.type, OWL.DatatypeProperty) in exporter.graph

    def test_default_roles_created(self, sample_ontology):
        """Test that default roles are created as User subclasses."""
        exporter = OWLExporter(sample_ontology)
        exporter.export()

        user_uri = exporter.ont.User

        for role in exporter.default_roles:
            role_uri = exporter.ont[exporter._safe_name(role)]
            assert (role_uri, RDF.type, OWL.Class) in exporter.graph
            assert (role_uri, RDFS.subClassOf, user_uri) in exporter.graph

    def test_crud_actions_generated(self, sample_ontology):
        """Test that CRUD action rules are generated for each entity."""
        exporter = OWLExporter(sample_ontology)
        exporter.export()

        # Check that read action exists for first entity
        if sample_ontology.entities:
            entity = sample_ontology.entities[0]
            entity_name = exporter._safe_name(entity.name)
            role_name = exporter._safe_name(exporter.default_roles[0])

            # Check read action
            read_action = exporter.ont[f"read_{entity_name}_{role_name}"]
            assert (read_action, RDF.type, exporter.ont.ReadAction) in exporter.graph

            # Check action has appliesTo
            entity_uri = exporter.ont[entity_name]
            assert (read_action, exporter.ont.appliesTo, entity_uri) in exporter.graph

            # Check action has requiresRole
            role_uri = exporter.ont[role_name]
            assert (read_action, exporter.ont.requiresRole, role_uri) in exporter.graph


class TestOWLExporterConstraints:
    """Test constraint handling in OWL export."""

    @pytest.fixture
    def ontology_with_constraints(self):
        """Create ontology with constraints for testing."""
        return Ontology(
            name="Constraint_Test",
            version="1.0",
            source="test",
            entities=[
                OntologyEntity(
                    name="User",
                    description="User entity",
                    properties=[
                        OntologyProperty(
                            name="email",
                            data_type="String",
                            required=True,
                            unique=True,
                            constraints=[
                                Constraint(
                                    type="regex",
                                    value=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
                                    message="Invalid email format",
                                )
                            ],
                        ),
                        OntologyProperty(
                            name="age",
                            data_type="Integer",
                            required=False,
                            constraints=[
                                Constraint(
                                    type="range",
                                    value={"min": 0, "max": 150},
                                    message="Age must be between 0 and 150",
                                )
                            ],
                        ),
                        OntologyProperty(
                            name="status",
                            data_type="String",
                            constraints=[
                                Constraint(
                                    type="enum",
                                    value=["active", "inactive", "pending"],
                                    message="Invalid status",
                                )
                            ],
                        ),
                    ],
                    constraints=[],
                ),
            ],
            relationships=[],
            business_rules=[],
        )

    def test_required_property_creates_cardinality(self, ontology_with_constraints):
        """Test that required property creates minCardinality restriction."""
        exporter = OWLExporter(ontology_with_constraints)
        exporter.export()

        # Required property should create cardinality restriction
        # Check that Restriction exists in graph
        restrictions = list(exporter.graph.subjects(RDF.type, OWL.Restriction))
        assert len(restrictions) > 0

    def test_unique_property_is_functional(self, ontology_with_constraints):
        """Test that unique property is marked as FunctionalProperty."""
        exporter = OWLExporter(ontology_with_constraints)
        exporter.export()

        # email property should be functional
        email_uri = exporter.ont["User_email"]
        assert (email_uri, RDF.type, OWL.FunctionalProperty) in exporter.graph

    def test_range_constraint_added(self, ontology_with_constraints):
        """Test that range constraint adds min/max values."""
        exporter = OWLExporter(ontology_with_constraints)
        exporter.export()

        # age property should have min/max values
        age_uri = exporter.ont["User_age"]
        min_triples = list(exporter.graph.triples((age_uri, exporter.ont.minValue, None)))
        max_triples = list(exporter.graph.triples((age_uri, exporter.ont.maxValue, None)))

        assert len(min_triples) > 0
        assert len(max_triples) > 0

    def test_regex_constraint_added(self, ontology_with_constraints):
        """Test that regex constraint adds pattern annotation."""
        exporter = OWLExporter(ontology_with_constraints)
        exporter.export()

        # email property should have pattern
        email_uri = exporter.ont["User_email"]
        pattern_triples = list(exporter.graph.triples((email_uri, exporter.ont.pattern, None)))

        assert len(pattern_triples) > 0

    def test_enum_constraint_added(self, ontology_with_constraints):
        """Test that enum constraint adds enumValue annotations."""
        exporter = OWLExporter(ontology_with_constraints)
        exporter.export()

        # status property should have enum values
        status_uri = exporter.ont["User_status"]

        # Check for at least one enumValue
        enum_found = False
        for pred, _ in exporter.graph.predicate_objects(status_uri):
            if "enumValue" in str(pred):
                enum_found = True
                break
        assert enum_found

    def test_constraint_message_added(self, ontology_with_constraints):
        """Test that constraint message is added."""
        exporter = OWLExporter(ontology_with_constraints)
        exporter.export()

        # email property should have constraint message
        email_uri = exporter.ont["User_email"]
        message_triples = list(
            exporter.graph.triples((email_uri, exporter.ont.constraintMessage, None))
        )

        assert len(message_triples) > 0


class TestOWLExporterBusinessRules:
    """Test business rules conversion to OWL."""

    @pytest.fixture
    def ontology_with_business_rules(self):
        """Create ontology with business rules for testing."""
        return Ontology(
            name="BusinessRules_Test",
            version="1.0",
            source="test",
            entities=[
                OntologyEntity(
                    name="Order",
                    description="Order entity",
                    properties=[
                        OntologyProperty(name="amount", data_type="Decimal"),
                        OntologyProperty(name="status", data_type="String"),
                    ],
                    constraints=[],
                ),
            ],
            relationships=[],
            business_rules=[
                BusinessRule(
                    name="HighValueOrder",
                    entity="Order",
                    condition="amount > 10000",
                    action="RequireApproval",
                    classification="high",
                    description="High value orders require manager approval",
                    priority=1,
                ),
                BusinessRule(
                    name="AutoApproveSmall",
                    entity="Order",
                    condition="amount < 100",
                    action="AutoApprove",
                    classification="low",
                    priority=2,
                ),
            ],
        )

    def test_business_rule_class_created(self, ontology_with_business_rules):
        """Test that business rule creates OWL class."""
        exporter = OWLExporter(ontology_with_business_rules)
        exporter.export()

        # HighValueOrderRule class should exist
        rule_class = exporter.ont["HighValueOrderRule"]
        assert (rule_class, RDF.type, OWL.Class) in exporter.graph
        assert (rule_class, RDFS.subClassOf, exporter.ont.Action) in exporter.graph

    def test_business_rule_instance_created(self, ontology_with_business_rules):
        """Test that business rule creates instance."""
        exporter = OWLExporter(ontology_with_business_rules)
        exporter.export()

        # Rule instance should exist
        rule_instance = exporter.ont["HighValueOrderRuleInstance"]
        rule_class = exporter.ont["HighValueOrderRule"]
        assert (rule_instance, RDF.type, rule_class) in exporter.graph

    def test_business_rule_applies_to_entity(self, ontology_with_business_rules):
        """Test that business rule links to entity."""
        exporter = OWLExporter(ontology_with_business_rules)
        exporter.export()

        rule_instance = exporter.ont["HighValueOrderRuleInstance"]
        order_uri = exporter.ont["Order"]
        assert (rule_instance, exporter.ont.appliesTo, order_uri) in exporter.graph

    def test_business_rule_condition_added(self, ontology_with_business_rules):
        """Test that business rule condition is added."""
        exporter = OWLExporter(ontology_with_business_rules)
        exporter.export()

        rule_instance = exporter.ont["HighValueOrderRuleInstance"]
        condition_triples = list(
            exporter.graph.triples((rule_instance, exporter.ont.condition, None))
        )

        assert len(condition_triples) > 0
        assert "amount > 10000" in str(condition_triples[0][2])


class TestOWLExporterRLS:
    """Test RLS (Row-Level Security) rules handling."""

    @pytest.fixture
    def sample_security_rules(self):
        """Create sample RLS rules for testing."""
        # Mock SecurityRule objects
        class MockSecurityRule:
            def __init__(self, role, table, dax_filter, description=""):
                self.role = role
                self.table = table
                self.dax_filter = dax_filter
                self.description = description

        return [
            MockSecurityRule(
                role="SalesManager",
                table="Orders",
                dax_filter="[Region] = USERPRINCIPALNAME()",
                description="Sales managers see only their region",
            ),
            MockSecurityRule(
                role="Analyst",
                table="Customers",
                dax_filter="[IsActive] = TRUE()",
                description="Analysts see only active customers",
            ),
        ]

    def test_add_rls_rules(self, sample_ontology, sample_security_rules):
        """Test adding RLS rules."""
        exporter = OWLExporter(sample_ontology)
        exporter.export()
        exporter.add_rls_rules(sample_security_rules)

        # Check SalesManager role was created
        role_uri = exporter.ont["SalesManager"]
        assert (role_uri, RDF.type, OWL.Class) in exporter.graph
        assert (role_uri, RDFS.subClassOf, exporter.ont.User) in exporter.graph

    def test_rls_action_rule_created(self, sample_ontology, sample_security_rules):
        """Test that RLS creates action rule."""
        exporter = OWLExporter(sample_ontology)
        exporter.export()
        exporter.add_rls_rules(sample_security_rules)

        # Check RLS action rule
        rls_uri = exporter.ont["RLS_SalesManager_Orders"]
        assert (rls_uri, RDF.type, exporter.ont.ReadAction) in exporter.graph

    def test_rls_dax_filter_added(self, sample_ontology, sample_security_rules):
        """Test that DAX filter is added to RLS rule."""
        exporter = OWLExporter(sample_ontology)
        exporter.export()
        exporter.add_rls_rules(sample_security_rules)

        # Check DAX filter
        rls_uri = exporter.ont["RLS_SalesManager_Orders"]
        filter_triples = list(
            exporter.graph.triples((rls_uri, exporter.ont.daxFilter, None))
        )

        assert len(filter_triples) > 0
        assert "USERPRINCIPALNAME" in str(filter_triples[0][2])

    def test_rls_marked_as_rls_rule(self, sample_ontology, sample_security_rules):
        """Test that RLS rule is marked with isRLSRule annotation."""
        exporter = OWLExporter(sample_ontology)
        exporter.export()
        exporter.add_rls_rules(sample_security_rules)

        rls_uri = exporter.ont["RLS_SalesManager_Orders"]
        rls_flag_triples = list(
            exporter.graph.triples((rls_uri, exporter.ont.isRLSRule, None))
        )

        assert len(rls_flag_triples) > 0


class TestOWLExporterSummary:
    """Test export summary functionality."""

    def test_get_export_summary(self, sample_ontology):
        """Test getting export summary."""
        exporter = OWLExporter(sample_ontology)
        summary = exporter.get_export_summary()

        assert summary["ontology_name"] == sample_ontology.name
        assert summary["total_triples"] > 0
        assert summary["classes"] > 0
        assert summary["entities"] == len(sample_ontology.entities)
        assert summary["relationships"] == len(sample_ontology.relationships)
        assert summary["default_roles"] == exporter.default_roles

    def test_summary_counts_action_rules(self, sample_ontology):
        """Test that summary counts action rules correctly."""
        exporter = OWLExporter(sample_ontology)
        summary = exporter.get_export_summary()

        # Should have CRUD actions for each entity * each role
        expected_min = len(sample_ontology.entities) * len(exporter.default_roles) * 4
        assert summary["action_rules"] >= expected_min


class TestOWLExporterRDFLibParseable:
    """Test that generated OWL can be parsed by RDFLib."""

    def test_owl_can_be_parsed_xml(self, sample_ontology):
        """Test that XML OWL can be parsed."""
        exporter = OWLExporter(sample_ontology)
        owl_content = exporter.export(format="xml")

        g = Graph()
        g.parse(data=owl_content, format="xml")

        assert len(g) > 0

    def test_owl_can_be_parsed_turtle(self, sample_ontology):
        """Test that Turtle OWL can be parsed."""
        exporter = OWLExporter(sample_ontology)
        owl_content = exporter.export(format="turtle")

        g = Graph()
        g.parse(data=owl_content, format="turtle")

        assert len(g) > 0
