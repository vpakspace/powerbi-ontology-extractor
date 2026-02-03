"""
Fabric IQ JSON → OWL Converter

Converts Fabric IQ JSON format to OntoGuard-compatible OWL format.
This enables Power BI ontologies to be validated by OntoGuard semantic firewall.

Key mappings:
- entities → owl:Class
- properties → owl:DatatypeProperty
- relationships → owl:ObjectProperty
- businessRules → Action classes with requiresRole/appliesTo
- permissions → Action individuals with role constraints
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD

logger = logging.getLogger(__name__)


class FabricIQToOWLConverter:
    """
    Converts Fabric IQ JSON to OntoGuard-compatible OWL format.

    This is the bridge between Power BI semantic models and OntoGuard
    semantic firewall for AI agents.

    Example:
        converter = FabricIQToOWLConverter(fabric_iq_json)
        owl_content = converter.convert(format="xml")
        converter.save("output.owl")
    """

    # OntoGuard namespace for action rules
    ONTOGUARD_NS = "http://example.org/ontoguard#"

    def __init__(self, fabric_iq_json: Dict[str, Any], base_uri: Optional[str] = None):
        """
        Initialize converter.

        Args:
            fabric_iq_json: Fabric IQ JSON from FabricIQExporter.export()
            base_uri: Optional base URI for the ontology (defaults to ontology name)
        """
        self.fabric_iq = fabric_iq_json
        self.graph = Graph()

        # Create namespace
        ontology_name = fabric_iq_json.get("ontologyItem", "powerbi_ontology")
        safe_name = ontology_name.replace(" ", "_").replace("-", "_")
        self.base_uri = base_uri or f"http://example.org/powerbi/{safe_name}#"

        self.ont = Namespace(self.base_uri)
        self.ontoguard = Namespace(self.ONTOGUARD_NS)

        # Bind namespaces for cleaner output
        self.graph.bind("ont", self.ont)
        self.graph.bind("ontoguard", self.ontoguard)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("xsd", XSD)

    def convert(self, format: str = "xml") -> str:
        """
        Convert Fabric IQ JSON to OWL format.

        Args:
            format: Output format ("xml", "turtle", "json-ld", "n3")

        Returns:
            OWL content as string
        """
        logger.info(f"Converting Fabric IQ to OWL format ({format})")

        # Add ontology metadata
        self._add_ontology_metadata()

        # Add base classes (User roles, Action)
        self._add_base_classes()

        # Add OntoGuard properties (requiresRole, appliesTo)
        self._add_ontoguard_properties()

        # Convert entities to OWL classes
        for entity in self.fabric_iq.get("entities", []):
            self._add_entity_class(entity)

        # Convert relationships to OWL object properties
        for rel in self.fabric_iq.get("relationships", []):
            self._add_relationship(rel)

        # Convert business rules to action rules
        for rule in self.fabric_iq.get("businessRules", []):
            self._add_action_rule(rule)

        # Add schema bindings as annotations (for drift detection)
        self._add_schema_bindings()

        return self.graph.serialize(format=format)

    def _add_ontology_metadata(self):
        """Add OWL ontology metadata."""
        ontology_uri = URIRef(self.base_uri.rstrip("#"))

        self.graph.add((ontology_uri, RDF.type, OWL.Ontology))
        self.graph.add((ontology_uri, RDFS.label, Literal(
            self.fabric_iq.get("ontologyItem", "Power BI Ontology")
        )))
        self.graph.add((ontology_uri, RDFS.comment, Literal(
            f"Ontology extracted from {self.fabric_iq.get('source', 'Power BI')}"
        )))
        self.graph.add((ontology_uri, OWL.versionInfo, Literal(
            self.fabric_iq.get("version", "1.0")
        )))

        # Add extraction timestamp
        extracted_date = self.fabric_iq.get("extractedDate", datetime.now().isoformat())
        self.graph.add((ontology_uri, self.ont.extractedDate, Literal(
            extracted_date, datatype=XSD.dateTime
        )))

    def _add_base_classes(self):
        """Add base classes for OntoGuard compatibility."""
        # User class (base for roles)
        user_uri = self.ont.User
        self.graph.add((user_uri, RDF.type, OWL.Class))
        self.graph.add((user_uri, RDFS.label, Literal("User")))
        self.graph.add((user_uri, RDFS.comment, Literal(
            "Base class for all user roles"
        )))

        # Standard roles (subclasses of User)
        roles = ["Admin", "Analyst", "Viewer", "Editor", "Owner"]
        for role in roles:
            role_uri = self.ont[role]
            self.graph.add((role_uri, RDF.type, OWL.Class))
            self.graph.add((role_uri, RDFS.subClassOf, user_uri))
            self.graph.add((role_uri, RDFS.label, Literal(role)))

        # Action class (base for all actions)
        action_uri = self.ont.Action
        self.graph.add((action_uri, RDF.type, OWL.Class))
        self.graph.add((action_uri, RDFS.label, Literal("Action")))
        self.graph.add((action_uri, RDFS.comment, Literal(
            "Base class for all actions that can be performed"
        )))

        # Standard action subclasses
        actions = ["ReadAction", "WriteAction", "DeleteAction", "ExecuteAction"]
        for action in actions:
            action_class_uri = self.ont[action]
            self.graph.add((action_class_uri, RDF.type, OWL.Class))
            self.graph.add((action_class_uri, RDFS.subClassOf, action_uri))
            self.graph.add((action_class_uri, RDFS.label, Literal(action)))

    def _add_ontoguard_properties(self):
        """Add OntoGuard action permission properties."""
        # requiresRole property
        requires_role = self.ont.requiresRole
        self.graph.add((requires_role, RDF.type, OWL.ObjectProperty))
        self.graph.add((requires_role, RDFS.label, Literal("requires role")))
        self.graph.add((requires_role, RDFS.comment, Literal(
            "Specifies which user role is required to perform an action"
        )))
        self.graph.add((requires_role, RDFS.domain, self.ont.Action))
        self.graph.add((requires_role, RDFS.range, self.ont.User))

        # appliesTo property
        applies_to = self.ont.appliesTo
        self.graph.add((applies_to, RDF.type, OWL.ObjectProperty))
        self.graph.add((applies_to, RDFS.label, Literal("applies to")))
        self.graph.add((applies_to, RDFS.comment, Literal(
            "Specifies which entity type an action can be applied to"
        )))
        self.graph.add((applies_to, RDFS.domain, self.ont.Action))
        self.graph.add((applies_to, RDFS.range, OWL.Thing))

        # requiresApproval property (for business rules)
        requires_approval = self.ont.requiresApproval
        self.graph.add((requires_approval, RDF.type, OWL.ObjectProperty))
        self.graph.add((requires_approval, RDFS.label, Literal("requires approval")))
        self.graph.add((requires_approval, RDFS.comment, Literal(
            "Indicates that an action requires approval from a specific role"
        )))
        self.graph.add((requires_approval, RDFS.domain, self.ont.Action))
        self.graph.add((requires_approval, RDFS.range, self.ont.User))

        # allowsAction property (for specifying action type)
        allows_action = self.ont.allowsAction
        self.graph.add((allows_action, RDF.type, OWL.DatatypeProperty))
        self.graph.add((allows_action, RDFS.label, Literal("allows action")))
        self.graph.add((allows_action, RDFS.comment, Literal(
            "Specifies the action type: read, create, update, delete"
        )))
        self.graph.add((allows_action, RDFS.domain, self.ont.Action))
        self.graph.add((allows_action, RDFS.range, XSD.string))

    def _add_entity_class(self, entity: Dict[str, Any]):
        """Convert Fabric IQ entity to OWL class with properties."""
        entity_name = entity.get("name", "")
        if not entity_name:
            return

        # Make valid URI
        safe_name = self._safe_uri_name(entity_name)
        entity_uri = self.ont[safe_name]

        # Entity is a class
        self.graph.add((entity_uri, RDF.type, OWL.Class))
        self.graph.add((entity_uri, RDFS.label, Literal(entity_name)))

        if entity.get("description"):
            self.graph.add((entity_uri, RDFS.comment, Literal(entity["description"])))

        # Add entity type annotation
        if entity.get("entityType"):
            self.graph.add((entity_uri, self.ont.entityType, Literal(entity["entityType"])))

        # Add source table annotation (for schema binding)
        if entity.get("source"):
            self.graph.add((entity_uri, self.ont.sourceTable, Literal(entity["source"])))

        # Add properties as datatype properties
        for prop in entity.get("properties", []):
            self._add_property(entity_uri, safe_name, prop)

        # Generate default action rules for this entity
        self._generate_entity_action_rules(safe_name, entity)

    def _add_property(self, entity_uri: URIRef, entity_name: str, prop: Dict[str, Any]):
        """Add property as OWL datatype property."""
        prop_name = prop.get("name", "")
        if not prop_name:
            return

        safe_prop_name = self._safe_uri_name(f"{entity_name}_{prop_name}")
        prop_uri = self.ont[safe_prop_name]

        self.graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))
        self.graph.add((prop_uri, RDFS.label, Literal(prop_name)))
        self.graph.add((prop_uri, RDFS.domain, entity_uri))

        # Map data type to XSD
        xsd_type = self._map_to_xsd(prop.get("type", "String"))
        self.graph.add((prop_uri, RDFS.range, xsd_type))

        if prop.get("description"):
            self.graph.add((prop_uri, RDFS.comment, Literal(prop["description"])))

        # Add constraints as annotations
        for constraint in prop.get("constraints", []):
            self._add_constraint(prop_uri, constraint)

    def _add_constraint(self, prop_uri: URIRef, constraint: Dict[str, Any]):
        """Add property constraint as OWL annotation."""
        constraint_type = constraint.get("type", "")
        constraint_value = constraint.get("value")

        if constraint_type == "range" and isinstance(constraint_value, dict):
            if "min" in constraint_value:
                self.graph.add((prop_uri, self.ont.minValue, Literal(
                    constraint_value["min"], datatype=XSD.decimal
                )))
            if "max" in constraint_value:
                self.graph.add((prop_uri, self.ont.maxValue, Literal(
                    constraint_value["max"], datatype=XSD.decimal
                )))
        elif constraint_type == "required":
            self.graph.add((prop_uri, self.ont.isRequired, Literal(True, datatype=XSD.boolean)))
        elif constraint_type == "unique":
            self.graph.add((prop_uri, self.ont.isUnique, Literal(True, datatype=XSD.boolean)))

    def _add_relationship(self, rel: Dict[str, Any]):
        """Add relationship as OWL object property."""
        rel_type = rel.get("type", "relatedTo")
        from_entity = rel.get("from", "")
        to_entity = rel.get("to", "")

        if not from_entity or not to_entity:
            return

        safe_rel_name = self._safe_uri_name(f"{from_entity}_{rel_type}_{to_entity}")
        rel_uri = self.ont[safe_rel_name]
        from_uri = self.ont[self._safe_uri_name(from_entity)]
        to_uri = self.ont[self._safe_uri_name(to_entity)]

        self.graph.add((rel_uri, RDF.type, OWL.ObjectProperty))
        self.graph.add((rel_uri, RDFS.label, Literal(rel_type)))
        self.graph.add((rel_uri, RDFS.domain, from_uri))
        self.graph.add((rel_uri, RDFS.range, to_uri))

        if rel.get("description"):
            self.graph.add((rel_uri, RDFS.comment, Literal(rel["description"])))

        # Add cardinality annotation
        if rel.get("cardinality"):
            self.graph.add((rel_uri, self.ont.cardinality, Literal(rel["cardinality"])))

    def _add_action_rule(self, rule: Dict[str, Any]):
        """Convert business rule to OntoGuard action rule."""
        rule_name = rule.get("name", "")
        if not rule_name:
            return

        safe_name = self._safe_uri_name(rule_name)

        # Create action class
        action_class_uri = self.ont[f"{safe_name}Action"]
        self.graph.add((action_class_uri, RDF.type, OWL.Class))
        self.graph.add((action_class_uri, RDFS.subClassOf, self.ont.Action))
        self.graph.add((action_class_uri, RDFS.label, Literal(rule_name)))

        if rule.get("description"):
            self.graph.add((action_class_uri, RDFS.comment, Literal(rule["description"])))

        # Create action individual with requiresRole and appliesTo
        action_uri = self.ont[f"{safe_name}ActionInstance"]
        self.graph.add((action_uri, RDF.type, action_class_uri))
        self.graph.add((action_uri, RDFS.label, Literal(f"{rule_name} action")))

        # Map action type
        action_type = rule.get("action", "").lower()
        if action_type:
            self.graph.add((action_uri, self.ont.allowsAction, Literal(action_type)))

        # Add entity (appliesTo)
        entity = rule.get("entity", "")
        if entity:
            entity_uri = self.ont[self._safe_uri_name(entity)]
            self.graph.add((action_uri, self.ont.appliesTo, entity_uri))

        # Determine required role from classification or triggers
        classification = rule.get("classification", "").lower()
        triggers = rule.get("triggers", [])

        # Map classification to required role
        role_mapping = {
            "critical": "Admin",
            "high": "Admin",
            "medium": "Editor",
            "low": "Viewer",
            "notify": "Analyst",
        }

        required_role = role_mapping.get(classification, "Viewer")
        if "NotifyOperations" in triggers:
            required_role = "Admin"

        role_uri = self.ont[required_role]
        self.graph.add((action_uri, self.ont.requiresRole, role_uri))

        # Add condition as annotation
        if rule.get("condition"):
            self.graph.add((action_uri, self.ont.ruleCondition, Literal(rule["condition"])))

    def _generate_entity_action_rules(self, entity_name: str, entity: Dict[str, Any]):  # noqa: ARG002
        """Generate default CRUD action rules for an entity."""
        # Standard actions: read, create, update, delete
        actions = [
            ("read", "Viewer"),
            ("create", "Editor"),
            ("update", "Editor"),
            ("delete", "Admin"),
        ]

        entity_uri = self.ont[entity_name]

        for action, default_role in actions:
            # Create action individual
            action_name = f"{action}_{entity_name}"
            action_uri = self.ont[self._safe_uri_name(action_name)]

            # Determine action class
            action_class = {
                "read": self.ont.ReadAction,
                "create": self.ont.WriteAction,
                "update": self.ont.WriteAction,
                "delete": self.ont.DeleteAction,
            }.get(action, self.ont.Action)

            self.graph.add((action_uri, RDF.type, action_class))
            self.graph.add((action_uri, RDFS.label, Literal(f"{action} {entity_name}")))
            self.graph.add((action_uri, self.ont.allowsAction, Literal(action)))
            self.graph.add((action_uri, self.ont.appliesTo, entity_uri))
            self.graph.add((action_uri, self.ont.requiresRole, self.ont[default_role]))

    def _add_schema_bindings(self):
        """Add schema bindings as annotations for drift detection."""
        data_bindings = self.fabric_iq.get("dataBindings", {})

        for entity_name, binding in data_bindings.items():
            entity_uri = self.ont[self._safe_uri_name(entity_name)]

            if binding.get("source"):
                self.graph.add((entity_uri, self.ont.schemaSource, Literal(binding["source"])))

            # Add column mappings
            for prop_name, column_name in binding.get("mapping", {}).items():
                prop_uri = self.ont[self._safe_uri_name(f"{entity_name}_{prop_name}")]
                self.graph.add((prop_uri, self.ont.sourceColumn, Literal(column_name)))

    def _safe_uri_name(self, name: str) -> str:
        """Convert name to valid URI component."""
        # Replace spaces and special characters
        safe = name.replace(" ", "_").replace("-", "_").replace(".", "_")
        # Remove any remaining invalid characters
        safe = "".join(c for c in safe if c.isalnum() or c == "_")
        return safe

    def _map_to_xsd(self, data_type: str) -> URIRef:
        """Map Fabric IQ data type to XSD type."""
        type_mapping = {
            "String": XSD.string,
            "string": XSD.string,
            "Integer": XSD.integer,
            "integer": XSD.integer,
            "int": XSD.integer,
            "Decimal": XSD.decimal,
            "decimal": XSD.decimal,
            "float": XSD.decimal,
            "Double": XSD.double,
            "double": XSD.double,
            "Date": XSD.date,
            "date": XSD.date,
            "DateTime": XSD.dateTime,
            "dateTime": XSD.dateTime,
            "Boolean": XSD.boolean,
            "boolean": XSD.boolean,
            "bool": XSD.boolean,
        }
        return type_mapping.get(data_type, XSD.string)

    def save(self, filepath: str, format: str = "xml"):
        """
        Save OWL export to file.

        Args:
            filepath: Path to save file
            format: Output format ("xml", "turtle", "json-ld", "n3")
        """
        output = self.convert(format=format)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(output)
        logger.info(f"Saved OWL export to {filepath}")

    @classmethod
    def from_fabric_iq_exporter(cls, exporter, base_uri: Optional[str] = None):
        """
        Create converter from FabricIQExporter instance.

        Args:
            exporter: FabricIQExporter instance
            base_uri: Optional base URI

        Returns:
            FabricIQToOWLConverter instance
        """
        fabric_iq_json = exporter.export()
        return cls(fabric_iq_json, base_uri)
