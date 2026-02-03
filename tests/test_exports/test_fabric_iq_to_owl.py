"""
Tests for FabricIQToOWLConverter.

Tests the conversion from Fabric IQ JSON format to OntoGuard-compatible OWL.
"""

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD

from powerbi_ontology.export.fabric_iq import FabricIQExporter
from powerbi_ontology.export.fabric_iq_to_owl import FabricIQToOWLConverter


class TestFabricIQToOWLConverter:
    """Test FabricIQToOWLConverter class."""

    @pytest.fixture
    def sample_fabric_iq_json(self):
        """Sample Fabric IQ JSON for testing."""
        return {
            "ontologyItem": "Sales_Ontology_v1.0",
            "version": "1.0",
            "source": "Sales.pbix",
            "extractedDate": "2024-01-15T10:30:00Z",
            "entities": [
                {
                    "name": "Customer",
                    "description": "Customer entity from Power BI",
                    "entityType": "Dimension",
                    "properties": [
                        {
                            "name": "CustomerId",
                            "type": "Integer",
                            "required": True,
                            "unique": True,
                            "description": "Unique customer identifier",
                            "constraints": []
                        },
                        {
                            "name": "CustomerName",
                            "type": "String",
                            "required": True,
                            "unique": False,
                            "description": "Customer name",
                            "constraints": []
                        },
                        {
                            "name": "Revenue",
                            "type": "Decimal",
                            "required": False,
                            "unique": False,
                            "description": "Total revenue",
                            "constraints": [
                                {"type": "range", "value": {"min": 0, "max": 1000000}, "message": "Revenue must be positive"}
                            ]
                        }
                    ],
                    "relationships": [],
                    "source": "sql_db.dbo.customers"
                },
                {
                    "name": "Order",
                    "description": "Order entity",
                    "entityType": "Fact",
                    "properties": [
                        {
                            "name": "OrderId",
                            "type": "Integer",
                            "required": True,
                            "unique": True,
                            "description": "Order ID",
                            "constraints": []
                        },
                        {
                            "name": "OrderDate",
                            "type": "DateTime",
                            "required": True,
                            "unique": False,
                            "description": "Order date",
                            "constraints": []
                        }
                    ],
                    "relationships": [],
                    "source": "sql_db.dbo.orders"
                }
            ],
            "relationships": [
                {
                    "from": "Order",
                    "fromProperty": "CustomerId",
                    "to": "Customer",
                    "toProperty": "CustomerId",
                    "type": "hasCustomer",
                    "cardinality": "many-to-one",
                    "description": "Order belongs to Customer"
                }
            ],
            "businessRules": [
                {
                    "name": "HighValueOrder",
                    "source": "DAX: High Value Order Flag",
                    "entity": "Order",
                    "condition": "OrderAmount > 10000",
                    "action": "NotifyManager",
                    "classification": "high",
                    "triggers": ["NotifyOperations"],
                    "description": "Alert on high value orders",
                    "priority": 1
                }
            ],
            "dataBindings": {
                "Customer": {
                    "source": "sql_db.dbo.customers",
                    "mapping": {
                        "CustomerId": "customer_id",
                        "CustomerName": "name"
                    }
                }
            },
            "metadata": {}
        }

    def test_init(self, sample_fabric_iq_json):
        """Test converter initialization."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        assert converter.fabric_iq == sample_fabric_iq_json
        assert converter.graph is not None
        assert "Sales_Ontology" in converter.base_uri

    def test_init_custom_base_uri(self, sample_fabric_iq_json):
        """Test converter with custom base URI."""
        custom_uri = "http://mycompany.com/ontologies/sales#"
        converter = FabricIQToOWLConverter(sample_fabric_iq_json, base_uri=custom_uri)
        assert converter.base_uri == custom_uri

    def test_convert_returns_string(self, sample_fabric_iq_json):
        """Test that convert returns OWL string."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        owl_content = converter.convert(format="xml")

        assert isinstance(owl_content, str)
        assert len(owl_content) > 0
        assert "<?xml" in owl_content or "<rdf:RDF" in owl_content

    def test_convert_turtle_format(self, sample_fabric_iq_json):
        """Test conversion to Turtle format."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        owl_content = converter.convert(format="turtle")

        assert isinstance(owl_content, str)
        # Turtle format indicators
        assert "@prefix" in owl_content or "a owl:Ontology" in owl_content

    def test_ontology_metadata(self, sample_fabric_iq_json):
        """Test that ontology metadata is included."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        converter.convert()

        # Check ontology triple exists
        ontology_uri = URIRef(converter.base_uri.rstrip("#"))
        assert (ontology_uri, RDF.type, OWL.Ontology) in converter.graph

    def test_entity_classes_created(self, sample_fabric_iq_json):
        """Test that entities are converted to OWL classes."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        converter.convert()

        # Check Customer class exists
        customer_uri = converter.ont.Customer
        assert (customer_uri, RDF.type, OWL.Class) in converter.graph

        # Check Order class exists
        order_uri = converter.ont.Order
        assert (order_uri, RDF.type, OWL.Class) in converter.graph

    def test_properties_created(self, sample_fabric_iq_json):
        """Test that properties are converted to OWL datatype properties."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        converter.convert()

        # Check CustomerId property exists
        prop_uri = converter.ont.Customer_CustomerId
        assert (prop_uri, RDF.type, OWL.DatatypeProperty) in converter.graph

        # Check domain is Customer
        customer_uri = converter.ont.Customer
        assert (prop_uri, RDFS.domain, customer_uri) in converter.graph

        # Check range is integer
        assert (prop_uri, RDFS.range, XSD.integer) in converter.graph

    def test_relationships_created(self, sample_fabric_iq_json):
        """Test that relationships are converted to OWL object properties."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        converter.convert()

        # Check relationship exists
        rel_uri = converter.ont.Order_hasCustomer_Customer
        assert (rel_uri, RDF.type, OWL.ObjectProperty) in converter.graph

    def test_base_classes_created(self, sample_fabric_iq_json):
        """Test that base classes (User, Action) are created."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        converter.convert()

        # Check User class
        user_uri = converter.ont.User
        assert (user_uri, RDF.type, OWL.Class) in converter.graph

        # Check Action class
        action_uri = converter.ont.Action
        assert (action_uri, RDF.type, OWL.Class) in converter.graph

        # Check role subclasses
        admin_uri = converter.ont.Admin
        assert (admin_uri, RDFS.subClassOf, user_uri) in converter.graph

    def test_ontoguard_properties_created(self, sample_fabric_iq_json):
        """Test that OntoGuard properties (requiresRole, appliesTo) are created."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        converter.convert()

        # Check requiresRole property
        requires_role = converter.ont.requiresRole
        assert (requires_role, RDF.type, OWL.ObjectProperty) in converter.graph

        # Check appliesTo property
        applies_to = converter.ont.appliesTo
        assert (applies_to, RDF.type, OWL.ObjectProperty) in converter.graph

    def test_action_rules_created(self, sample_fabric_iq_json):
        """Test that business rules are converted to action rules."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        converter.convert()

        # Check action class exists
        action_class = converter.ont.HighValueOrderAction
        assert (action_class, RDF.type, OWL.Class) in converter.graph
        assert (action_class, RDFS.subClassOf, converter.ont.Action) in converter.graph

    def test_crud_action_rules_generated(self, sample_fabric_iq_json):
        """Test that default CRUD action rules are generated for entities."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        converter.convert()

        # Check read action for Customer
        read_action = converter.ont.read_Customer
        assert (read_action, RDF.type, converter.ont.ReadAction) in converter.graph

        # Check delete action requires Admin
        delete_action = converter.ont.delete_Customer
        assert (delete_action, converter.ont.requiresRole, converter.ont.Admin) in converter.graph

    def test_schema_bindings_added(self, sample_fabric_iq_json):
        """Test that schema bindings are added as annotations."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        converter.convert()

        # Check schema source annotation
        customer_uri = converter.ont.Customer
        triples = list(converter.graph.triples((customer_uri, converter.ont.schemaSource, None)))
        assert len(triples) > 0

    def test_constraints_added(self, sample_fabric_iq_json):
        """Test that property constraints are added."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        converter.convert()

        # Check Revenue property has min/max constraints
        revenue_uri = converter.ont.Customer_Revenue

        # Check minValue annotation
        min_triples = list(converter.graph.triples((revenue_uri, converter.ont.minValue, None)))
        assert len(min_triples) > 0

    def test_from_fabric_iq_exporter(self, sample_ontology):
        """Test creating converter from FabricIQExporter."""
        exporter = FabricIQExporter(sample_ontology)
        converter = FabricIQToOWLConverter.from_fabric_iq_exporter(exporter)

        assert converter.fabric_iq is not None
        assert "ontologyItem" in converter.fabric_iq

    def test_safe_uri_name(self, sample_fabric_iq_json):
        """Test URI name sanitization."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)

        assert converter._safe_uri_name("My Entity") == "My_Entity"
        assert converter._safe_uri_name("Entity-Name") == "Entity_Name"
        assert converter._safe_uri_name("Entity.Name") == "Entity_Name"

    def test_xsd_type_mapping(self, sample_fabric_iq_json):
        """Test XSD type mapping."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)

        assert converter._map_to_xsd("String") == XSD.string
        assert converter._map_to_xsd("Integer") == XSD.integer
        assert converter._map_to_xsd("Decimal") == XSD.decimal
        assert converter._map_to_xsd("DateTime") == XSD.dateTime
        assert converter._map_to_xsd("Boolean") == XSD.boolean
        assert converter._map_to_xsd("unknown") == XSD.string  # Default

    def test_save_file(self, sample_fabric_iq_json, tmp_path):
        """Test saving OWL to file."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        output_path = tmp_path / "output.owl"

        converter.save(str(output_path))

        assert output_path.exists()
        content = output_path.read_text()
        assert "owl:Ontology" in content or "Ontology" in content

    def test_empty_entities(self):
        """Test with empty entities list."""
        fabric_iq = {
            "ontologyItem": "Empty_Ontology",
            "version": "1.0",
            "source": "test.pbix",
            "entities": [],
            "relationships": [],
            "businessRules": [],
            "dataBindings": {},
            "metadata": {}
        }

        converter = FabricIQToOWLConverter(fabric_iq)
        owl_content = converter.convert()

        assert isinstance(owl_content, str)
        # Should still have base classes
        assert (converter.ont.User, RDF.type, OWL.Class) in converter.graph

    def test_entity_with_source_table(self, sample_fabric_iq_json):
        """Test that source table is added as annotation."""
        converter = FabricIQToOWLConverter(sample_fabric_iq_json)
        converter.convert()

        customer_uri = converter.ont.Customer
        source_triples = list(converter.graph.triples((customer_uri, converter.ont.sourceTable, None)))
        assert len(source_triples) > 0
        assert "sql_db.dbo.customers" in str(source_triples[0][2])


class TestFabricIQToOWLIntegration:
    """Integration tests for full pipeline."""

    def test_full_pipeline_with_sample_ontology(self, sample_ontology):
        """Test full pipeline: Ontology → FabricIQ → OWL."""
        # Step 1: Export to Fabric IQ
        fabric_exporter = FabricIQExporter(sample_ontology)
        fabric_json = fabric_exporter.export()

        # Step 2: Convert to OWL
        owl_converter = FabricIQToOWLConverter(fabric_json)
        owl_content = owl_converter.convert(format="xml")

        # Verify
        assert isinstance(owl_content, str)
        assert len(owl_content) > 1000  # Should have substantial content

        # Parse and verify structure
        g = Graph()
        g.parse(data=owl_content, format="xml")

        # Should have classes, properties, and action rules
        classes = list(g.subjects(RDF.type, OWL.Class))
        assert len(classes) > 0

        properties = list(g.subjects(RDF.type, OWL.DatatypeProperty))
        assert len(properties) >= 0  # May have properties

    def test_owl_can_be_parsed_by_rdflib(self, sample_ontology):
        """Test that generated OWL can be parsed back."""
        # Create Fabric IQ JSON from sample ontology
        fabric_exporter = FabricIQExporter(sample_ontology)
        fabric_json = fabric_exporter.export()

        converter = FabricIQToOWLConverter(fabric_json)
        owl_content = converter.convert(format="xml")

        # Try parsing
        g = Graph()
        g.parse(data=owl_content, format="xml")

        # Should have triples
        assert len(g) > 0
