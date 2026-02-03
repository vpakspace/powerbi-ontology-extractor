"""
Tests for ContractToOWLConverter.

Tests the conversion from SemanticContract to OntoGuard-compatible OWL.
"""

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS, OWL

from powerbi_ontology.contract_builder import (
    ContractBuilder,
    SemanticContract,
    ContractPermissions,
    AuditConfig,
)
from powerbi_ontology.ontology_generator import BusinessRule
from powerbi_ontology.export.contract_to_owl import ContractToOWLConverter


class TestContractToOWLConverter:
    """Test ContractToOWLConverter class."""

    @pytest.fixture
    def sample_contract(self):
        """Sample SemanticContract for testing."""
        permissions = ContractPermissions(
            read_entities=["Customer", "Order", "Product"],
            write_properties={
                "Order": ["status", "notes"],
                "Customer": ["email", "phone"],
            },
            executable_actions=["approve_order", "send_notification"],
            required_role="SalesAgent",
            context_filters={
                "Order": "region = 'US'",
                "Customer": "active = true",
            },
        )

        business_rules = [
            BusinessRule(
                name="HighValueOrder",
                entity="Order",
                condition="amount > 10000",
                action="require_approval",
                classification="high",
                description="High value orders require manager approval",
            ),
            BusinessRule(
                name="CustomerUpdate",
                entity="Customer",
                condition="any_change",
                action="log_change",
                classification="medium",
                description="Log all customer updates",
            ),
        ]

        audit = AuditConfig(
            log_reads=True,
            log_writes=True,
            log_actions=True,
            alert_on_violation=True,
        )

        return SemanticContract(
            agent_name="Sales Agent",
            ontology_version="1.0",
            permissions=permissions,
            business_rules=business_rules,
            audit_settings=audit,
            metadata={
                "created_date": "2024-01-15T10:00:00Z",
                "ontology_source": "Sales.pbix",
            },
        )

    def test_init(self, sample_contract):
        """Test converter initialization."""
        converter = ContractToOWLConverter(sample_contract)

        assert converter.contract == sample_contract
        assert converter.graph is not None
        assert "Sales_Agent" in converter.base_uri

    def test_init_custom_base_uri(self, sample_contract):
        """Test converter with custom base URI."""
        custom_uri = "http://mycompany.com/contracts/sales#"
        converter = ContractToOWLConverter(sample_contract, base_uri=custom_uri)

        assert converter.base_uri == custom_uri

    def test_convert_returns_string(self, sample_contract):
        """Test that convert returns OWL string."""
        converter = ContractToOWLConverter(sample_contract)
        owl_content = converter.convert(format="xml")

        assert isinstance(owl_content, str)
        assert len(owl_content) > 0
        assert "<?xml" in owl_content or "<rdf:RDF" in owl_content

    def test_convert_turtle_format(self, sample_contract):
        """Test conversion to Turtle format."""
        converter = ContractToOWLConverter(sample_contract)
        owl_content = converter.convert(format="turtle")

        assert isinstance(owl_content, str)
        assert "@prefix" in owl_content or "a owl:Ontology" in owl_content

    def test_ontology_metadata(self, sample_contract):
        """Test that ontology metadata is included."""
        converter = ContractToOWLConverter(sample_contract)
        converter.convert()

        ontology_uri = URIRef(converter.base_uri.rstrip("#"))
        assert (ontology_uri, RDF.type, OWL.Ontology) in converter.graph

    def test_base_classes_created(self, sample_contract):
        """Test that base classes (User, Action) are created."""
        converter = ContractToOWLConverter(sample_contract)
        converter.convert()

        # Check User class
        user_uri = converter.ont.User
        assert (user_uri, RDF.type, OWL.Class) in converter.graph

        # Check Action class
        action_uri = converter.ont.Action
        assert (action_uri, RDF.type, OWL.Class) in converter.graph

        # Check required role subclass
        role_uri = converter.ont.SalesAgent
        assert (role_uri, RDFS.subClassOf, user_uri) in converter.graph

    def test_action_subclasses_created(self, sample_contract):
        """Test that action subclasses are created."""
        converter = ContractToOWLConverter(sample_contract)
        converter.convert()

        action_uri = converter.ont.Action

        for action_type in ["ReadAction", "WriteAction", "DeleteAction", "ExecuteAction"]:
            action_class = converter.ont[action_type]
            assert (action_class, RDF.type, OWL.Class) in converter.graph
            assert (action_class, RDFS.subClassOf, action_uri) in converter.graph

    def test_ontoguard_properties_created(self, sample_contract):
        """Test that OntoGuard properties (requiresRole, appliesTo) are created."""
        converter = ContractToOWLConverter(sample_contract)
        converter.convert()

        # Check requiresRole property
        requires_role = converter.ont.requiresRole
        assert (requires_role, RDF.type, OWL.ObjectProperty) in converter.graph

        # Check appliesTo property
        applies_to = converter.ont.appliesTo
        assert (applies_to, RDF.type, OWL.ObjectProperty) in converter.graph

        # Check allowsAction property
        allows_action = converter.ont.allowsAction
        assert (allows_action, RDF.type, OWL.DatatypeProperty) in converter.graph

    def test_entity_classes_created(self, sample_contract):
        """Test that entity classes are created from permissions."""
        converter = ContractToOWLConverter(sample_contract)
        converter.convert()

        # Check read entities
        for entity_name in ["Customer", "Order", "Product"]:
            entity_uri = converter.ont[entity_name]
            assert (entity_uri, RDF.type, OWL.Class) in converter.graph

    def test_read_permissions_converted(self, sample_contract):
        """Test that read_entities are converted to ReadAction rules."""
        converter = ContractToOWLConverter(sample_contract)
        converter.convert()

        # Check read action for Customer
        read_customer = converter.ont.read_Customer
        assert (read_customer, RDF.type, converter.ont.ReadAction) in converter.graph
        assert (read_customer, converter.ont.appliesTo, converter.ont.Customer) in converter.graph
        assert (read_customer, converter.ont.requiresRole, converter.ont.SalesAgent) in converter.graph

    def test_write_permissions_converted(self, sample_contract):
        """Test that write_properties are converted to WriteAction rules."""
        converter = ContractToOWLConverter(sample_contract)
        converter.convert()

        # Check write action for Order.status
        write_order_status = converter.ont.write_Order_status
        assert (write_order_status, RDF.type, converter.ont.WriteAction) in converter.graph
        assert (write_order_status, converter.ont.appliesTo, converter.ont.Order) in converter.graph

        # Check update action for Order
        update_order = converter.ont.update_Order
        assert (update_order, RDF.type, converter.ont.WriteAction) in converter.graph

    def test_executable_actions_converted(self, sample_contract):
        """Test that executable_actions are converted to ExecuteAction rules."""
        converter = ContractToOWLConverter(sample_contract)
        converter.convert()

        # Check approve_order action
        action_class = converter.ont.approve_orderAction
        assert (action_class, RDF.type, OWL.Class) in converter.graph
        assert (action_class, RDFS.subClassOf, converter.ont.ExecuteAction) in converter.graph

        # Check execute action individual
        execute_action = converter.ont.execute_approve_order
        assert (execute_action, RDF.type, action_class) in converter.graph
        assert (execute_action, converter.ont.requiresRole, converter.ont.SalesAgent) in converter.graph

    def test_business_rules_converted(self, sample_contract):
        """Test that business rules are converted to action rules."""
        converter = ContractToOWLConverter(sample_contract)
        converter.convert()

        # Check HighValueOrder rule class
        rule_class = converter.ont.HighValueOrderRule
        assert (rule_class, RDF.type, OWL.Class) in converter.graph
        assert (rule_class, RDFS.subClassOf, converter.ont.Action) in converter.graph

        # Check rule instance
        rule_instance = converter.ont.HighValueOrderRuleInstance
        assert (rule_instance, RDF.type, rule_class) in converter.graph
        assert (rule_instance, converter.ont.appliesTo, converter.ont.Order) in converter.graph

    def test_context_filters_added(self, sample_contract):
        """Test that context filters are added as annotations."""
        converter = ContractToOWLConverter(sample_contract)
        converter.convert()

        # Check context filter for Order
        order_uri = converter.ont.Order
        filter_triples = list(converter.graph.triples((order_uri, converter.ont.contextFilter, None)))
        assert len(filter_triples) > 0
        assert "region = 'US'" in str(filter_triples[0][2])

    def test_audit_config_added(self, sample_contract):
        """Test that audit configuration is added."""
        converter = ContractToOWLConverter(sample_contract)
        converter.convert()

        ontology_uri = URIRef(converter.base_uri.rstrip("#"))

        # Check audit settings
        assert len(list(converter.graph.triples((ontology_uri, converter.ont.auditLogReads, None)))) > 0
        assert len(list(converter.graph.triples((ontology_uri, converter.ont.auditLogWrites, None)))) > 0

    def test_safe_name(self, sample_contract):
        """Test URI name sanitization."""
        converter = ContractToOWLConverter(sample_contract)

        assert converter._safe_name("My Entity") == "My_Entity"
        assert converter._safe_name("Entity-Name") == "Entity_Name"
        assert converter._safe_name("Entity.Name") == "Entity_Name"
        assert converter._safe_name("Entity 123") == "Entity_123"

    def test_save_file(self, sample_contract, tmp_path):
        """Test saving OWL to file."""
        converter = ContractToOWLConverter(sample_contract)
        output_path = tmp_path / "contract.owl"

        converter.save(str(output_path))

        assert output_path.exists()
        content = output_path.read_text()
        assert "owl:Ontology" in content or "Ontology" in content

    def test_get_action_rules_summary(self, sample_contract):
        """Test getting action rules summary."""
        converter = ContractToOWLConverter(sample_contract)
        summary = converter.get_action_rules_summary()

        assert summary["agent_name"] == "Sales Agent"
        assert summary["required_role"] == "SalesAgent"
        assert summary["read_actions"] == 3  # Customer, Order, Product
        assert summary["write_actions"] > 0
        assert summary["business_rules"] == 2
        assert summary["total_triples"] > 0

    def test_empty_permissions(self):
        """Test with empty permissions."""
        permissions = ContractPermissions()
        contract = SemanticContract(
            agent_name="Empty Agent",
            ontology_version="1.0",
            permissions=permissions,
            business_rules=[],
            audit_settings=AuditConfig(),
            metadata={},
        )

        converter = ContractToOWLConverter(contract)
        owl_content = converter.convert()

        assert isinstance(owl_content, str)
        # Should still have base classes
        assert (converter.ont.User, RDF.type, OWL.Class) in converter.graph
        assert (converter.ont.Action, RDF.type, OWL.Class) in converter.graph

    def test_owl_can_be_parsed_by_rdflib(self, sample_contract):
        """Test that generated OWL can be parsed back."""
        converter = ContractToOWLConverter(sample_contract)
        owl_content = converter.convert(format="xml")

        # Try parsing
        g = Graph()
        g.parse(data=owl_content, format="xml")

        # Should have triples
        assert len(g) > 0


class TestContractToOWLIntegration:
    """Integration tests for Contract → OWL pipeline."""

    def test_contract_builder_to_owl(self, sample_ontology):
        """Test full pipeline: Ontology → ContractBuilder → OWL."""
        # Step 1: Build contract from ontology
        builder = ContractBuilder(sample_ontology)

        # Define permissions
        permissions = {
            "read": ["Customer", "Product"],
            "write": {"Customer": ["email"]},
            "execute": ["generate_report"],
            "role": "Analyst",
        }

        contract = builder.build_contract("AnalystAgent", permissions)

        # Step 2: Convert to OWL
        converter = ContractToOWLConverter(contract)
        owl_content = converter.convert(format="xml")

        # Verify
        assert isinstance(owl_content, str)
        assert len(owl_content) > 500

        # Parse and verify structure
        g = Graph()
        g.parse(data=owl_content, format="xml")

        # Should have classes and action rules
        classes = list(g.subjects(RDF.type, OWL.Class))
        assert len(classes) > 0

    def test_role_based_action_rules(self, sample_ontology):
        """Test that role-based action rules are correctly generated."""
        builder = ContractBuilder(sample_ontology)

        permissions = {
            "read": ["Order"],
            "write": {"Order": ["status"]},
            "role": "Manager",
        }

        contract = builder.build_contract("ManagerAgent", permissions)
        converter = ContractToOWLConverter(contract)
        converter.convert()

        # Check Manager role exists
        manager_uri = converter.ont.Manager
        assert (manager_uri, RDFS.subClassOf, converter.ont.User) in converter.graph

        # Check read action requires Manager role
        read_order = converter.ont.read_Order
        assert (read_order, converter.ont.requiresRole, manager_uri) in converter.graph
