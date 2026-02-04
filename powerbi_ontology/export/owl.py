"""
OWL/RDF Exporter

Exports ontologies to OWL/RDF format for semantic web standards.
Enhanced with action rules, constraints, and RLS support for OntoGuard integration.
"""

import logging
from typing import Optional, List

from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

from powerbi_ontology.ontology_generator import (
    Ontology,
    OntologyEntity,
    OntologyProperty,
    OntologyRelationship,
    BusinessRule,
    Constraint,
)

logger = logging.getLogger(__name__)


class OWLExporter:
    """
    Exports ontologies to OWL/RDF format.

    Uses RDFLib to generate standard OWL/RDF files compatible with
    triple stores, OntoGuard, and other semantic web tools.

    Enhanced features:
    - Action rules (requiresRole, appliesTo, allowsAction) for OntoGuard
    - Property constraints (required, range, enum)
    - RLS rules as OWL restrictions
    """

    def __init__(
        self,
        ontology: Ontology,
        base_uri: Optional[str] = None,
        include_action_rules: bool = True,
        include_constraints: bool = True,
        default_roles: Optional[List[str]] = None,
    ):
        """
        Initialize OWL exporter.

        Args:
            ontology: Ontology to export
            base_uri: Custom base URI (default: auto-generated)
            include_action_rules: Generate OntoGuard-compatible action rules
            include_constraints: Generate OWL restrictions for constraints
            default_roles: Default roles for action rules (default: Admin, Analyst, Viewer)
        """
        self.ontology = ontology
        self.graph = Graph()
        self.include_action_rules = include_action_rules
        self.include_constraints = include_constraints

        # Create namespace for this ontology
        safe_name = self._safe_name(ontology.name)
        self.base_uri = base_uri or f"http://example.com/ontologies/{safe_name}#"
        self.ont = Namespace(self.base_uri)

        # Bind namespace prefixes
        self.graph.bind("ont", self.ont)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("xsd", XSD)

        # Default roles for action rules
        self.default_roles = default_roles or ["Admin", "Analyst", "Viewer"]

    def export(self, format: str = "xml") -> str:
        """
        Export ontology to OWL/RDF format.

        Args:
            format: Output format ("xml", "turtle", "json-ld", "n3")

        Returns:
            OWL/RDF string
        """
        logger.info(f"Exporting ontology '{self.ontology.name}' to OWL format ({format})")

        # Add ontology metadata
        self._add_ontology_metadata()

        # Add base classes (User, Action hierarchy)
        if self.include_action_rules:
            self._add_base_classes()

        # Add entities (classes)
        for entity in self.ontology.entities:
            self._add_entity(entity)

        # Add relationships (object properties)
        for rel in self.ontology.relationships:
            self._add_relationship(rel)

        # Add business rules as action rules
        if self.include_action_rules:
            self._add_business_rules()
            self._add_default_crud_actions()

        # Serialize to requested format
        return self.graph.serialize(format=format)

    def _add_ontology_metadata(self):
        """Add ontology-level metadata."""
        ontology_uri = URIRef(self.base_uri.rstrip("#"))
        self.graph.add((ontology_uri, RDF.type, OWL.Ontology))
        self.graph.add((ontology_uri, RDFS.label, Literal(self.ontology.name)))
        self.graph.add((ontology_uri, RDFS.comment, Literal(f"Ontology from {self.ontology.source}")))

        # Add version
        if self.ontology.version:
            self.graph.add((ontology_uri, OWL.versionInfo, Literal(self.ontology.version)))

        # Add metadata as annotations
        for key, value in self.ontology.metadata.items():
            self.graph.add((ontology_uri, self.ont[f"meta_{key}"], Literal(str(value))))

    def _add_base_classes(self):
        """Add base classes for OntoGuard compatibility."""
        # User class (base for roles)
        user_uri = self.ont.User
        self.graph.add((user_uri, RDF.type, OWL.Class))
        self.graph.add((user_uri, RDFS.label, Literal("User")))
        self.graph.add((user_uri, RDFS.comment, Literal("Base class for user roles")))

        # Action class hierarchy
        action_uri = self.ont.Action
        self.graph.add((action_uri, RDF.type, OWL.Class))
        self.graph.add((action_uri, RDFS.label, Literal("Action")))
        self.graph.add((action_uri, RDFS.comment, Literal("Base class for actions")))

        # Action subclasses
        for action_type in ["ReadAction", "WriteAction", "DeleteAction", "ExecuteAction"]:
            action_class = self.ont[action_type]
            self.graph.add((action_class, RDF.type, OWL.Class))
            self.graph.add((action_class, RDFS.subClassOf, action_uri))
            self.graph.add((action_class, RDFS.label, Literal(action_type)))

        # OntoGuard properties
        requires_role = self.ont.requiresRole
        self.graph.add((requires_role, RDF.type, OWL.ObjectProperty))
        self.graph.add((requires_role, RDFS.label, Literal("requiresRole")))
        self.graph.add((requires_role, RDFS.comment, Literal("Role required to perform this action")))
        self.graph.add((requires_role, RDFS.domain, action_uri))
        self.graph.add((requires_role, RDFS.range, user_uri))

        applies_to = self.ont.appliesTo
        self.graph.add((applies_to, RDF.type, OWL.ObjectProperty))
        self.graph.add((applies_to, RDFS.label, Literal("appliesTo")))
        self.graph.add((applies_to, RDFS.comment, Literal("Entity this action applies to")))
        self.graph.add((applies_to, RDFS.domain, action_uri))

        allows_action = self.ont.allowsAction
        self.graph.add((allows_action, RDF.type, OWL.DatatypeProperty))
        self.graph.add((allows_action, RDFS.label, Literal("allowsAction")))
        self.graph.add((allows_action, RDFS.comment, Literal("Action type allowed")))
        self.graph.add((allows_action, RDFS.range, XSD.string))

        applies_to_property = self.ont.appliesToProperty
        self.graph.add((applies_to_property, RDF.type, OWL.DatatypeProperty))
        self.graph.add((applies_to_property, RDFS.label, Literal("appliesToProperty")))
        self.graph.add((applies_to_property, RDFS.comment, Literal("Property this action applies to")))
        self.graph.add((applies_to_property, RDFS.range, XSD.string))

        # Add default roles as User subclasses
        for role in self.default_roles:
            role_uri = self.ont[self._safe_name(role)]
            self.graph.add((role_uri, RDF.type, OWL.Class))
            self.graph.add((role_uri, RDFS.subClassOf, user_uri))
            self.graph.add((role_uri, RDFS.label, Literal(role)))

    def _add_entity(self, entity: OntologyEntity):
        """Add entity as OWL class with properties and constraints."""
        entity_uri = self.ont[self._safe_name(entity.name)]

        # Entity is a class
        self.graph.add((entity_uri, RDF.type, OWL.Class))
        self.graph.add((entity_uri, RDFS.label, Literal(entity.name)))
        if entity.description:
            self.graph.add((entity_uri, RDFS.comment, Literal(entity.description)))

        # Add entity type annotation
        if entity.entity_type:
            self.graph.add((entity_uri, self.ont.entityType, Literal(entity.entity_type)))

        # Add source table annotation
        if entity.source_table:
            self.graph.add((entity_uri, self.ont.sourceTable, Literal(entity.source_table)))

        # Add properties (datatype properties)
        for prop in entity.properties:
            self._add_property(entity, prop)

        # Add entity-level constraints
        if self.include_constraints:
            for constraint in entity.constraints:
                self._add_entity_constraint(entity_uri, constraint)

    def _add_property(self, entity: OntologyEntity, prop: OntologyProperty):
        """Add property as OWL datatype property with constraints."""
        entity_uri = self.ont[self._safe_name(entity.name)]
        prop_uri = self.ont[f"{self._safe_name(entity.name)}_{self._safe_name(prop.name)}"]

        self.graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))
        self.graph.add((prop_uri, RDFS.label, Literal(prop.name)))
        self.graph.add((prop_uri, RDFS.domain, entity_uri))

        # Map data type to XSD
        xsd_type = self._map_to_xsd(prop.data_type)
        self.graph.add((prop_uri, RDFS.range, xsd_type))

        if prop.description:
            self.graph.add((prop_uri, RDFS.comment, Literal(prop.description)))

        # Add source column annotation
        if prop.source_column:
            self.graph.add((prop_uri, self.ont.sourceColumn, Literal(prop.source_column)))

        # Add constraints
        if self.include_constraints:
            # Required property (minCardinality 1)
            if prop.required:
                self._add_cardinality_restriction(entity_uri, prop_uri, min_card=1)

            # Unique property (functional property)
            if prop.unique:
                self.graph.add((prop_uri, RDF.type, OWL.FunctionalProperty))

            # Property-level constraints
            for constraint in prop.constraints:
                self._add_property_constraint(prop_uri, constraint)

    def _add_cardinality_restriction(
        self,
        class_uri: URIRef,
        property_uri: URIRef,
        min_card: Optional[int] = None,
        max_card: Optional[int] = None,
    ):
        """Add cardinality restriction to a class."""
        restriction = BNode()
        self.graph.add((restriction, RDF.type, OWL.Restriction))
        self.graph.add((restriction, OWL.onProperty, property_uri))

        if min_card is not None:
            self.graph.add((restriction, OWL.minCardinality, Literal(min_card, datatype=XSD.nonNegativeInteger)))

        if max_card is not None:
            self.graph.add((restriction, OWL.maxCardinality, Literal(max_card, datatype=XSD.nonNegativeInteger)))

        self.graph.add((class_uri, RDFS.subClassOf, restriction))

    def _add_property_constraint(self, prop_uri: URIRef, constraint: Constraint):
        """Add property-level constraint as OWL annotation or restriction."""
        if constraint.type == "range":
            # Range constraint (min/max)
            if isinstance(constraint.value, dict):
                if "min" in constraint.value:
                    self.graph.add((
                        prop_uri,
                        self.ont.minValue,
                        Literal(constraint.value["min"], datatype=XSD.decimal)
                    ))
                if "max" in constraint.value:
                    self.graph.add((
                        prop_uri,
                        self.ont.maxValue,
                        Literal(constraint.value["max"], datatype=XSD.decimal)
                    ))

        elif constraint.type == "regex":
            # Regex pattern constraint
            pattern = constraint.value.get("pattern", str(constraint.value)) if isinstance(constraint.value, dict) else str(constraint.value)
            self.graph.add((prop_uri, self.ont.pattern, Literal(pattern)))

        elif constraint.type == "enum":
            # Enumeration constraint
            values = constraint.value if isinstance(constraint.value, list) else [constraint.value]
            for i, val in enumerate(values):
                self.graph.add((prop_uri, self.ont[f"enumValue_{i}"], Literal(str(val))))

        elif constraint.type == "reference":
            # Reference to another entity
            self.graph.add((prop_uri, self.ont.references, Literal(str(constraint.value))))

        # Add constraint message if present
        if constraint.message:
            self.graph.add((prop_uri, self.ont.constraintMessage, Literal(constraint.message)))

    def _add_entity_constraint(self, entity_uri: URIRef, constraint: Constraint):
        """Add entity-level constraint."""
        constraint_node = BNode()
        self.graph.add((constraint_node, RDF.type, self.ont.EntityConstraint))
        self.graph.add((constraint_node, self.ont.constraintType, Literal(constraint.type)))
        self.graph.add((constraint_node, self.ont.constraintValue, Literal(str(constraint.value))))
        if constraint.message:
            self.graph.add((constraint_node, RDFS.comment, Literal(constraint.message)))
        self.graph.add((entity_uri, self.ont.hasConstraint, constraint_node))

    def _add_relationship(self, rel: OntologyRelationship):
        """Add relationship as OWL object property."""
        rel_name = self._safe_name(f"{rel.from_entity}_{rel.relationship_type}_{rel.to_entity}")
        rel_uri = self.ont[rel_name]
        from_uri = self.ont[self._safe_name(rel.from_entity)]
        to_uri = self.ont[self._safe_name(rel.to_entity)]

        # Relationship is an object property
        self.graph.add((rel_uri, RDF.type, OWL.ObjectProperty))
        self.graph.add((rel_uri, RDFS.label, Literal(rel.relationship_type)))
        self.graph.add((rel_uri, RDFS.domain, from_uri))
        self.graph.add((rel_uri, RDFS.range, to_uri))

        if rel.description:
            self.graph.add((rel_uri, RDFS.comment, Literal(rel.description)))

        # Add source relationship annotation
        if rel.source_relationship:
            self.graph.add((rel_uri, self.ont.sourceRelationship, Literal(rel.source_relationship)))

        # Add cardinality annotations
        self.graph.add((rel_uri, self.ont.cardinality, Literal(rel.cardinality)))

        # Add from/to property annotations
        if rel.from_property:
            self.graph.add((rel_uri, self.ont.fromProperty, Literal(rel.from_property)))
        if rel.to_property:
            self.graph.add((rel_uri, self.ont.toProperty, Literal(rel.to_property)))

    def _add_business_rules(self):
        """Add business rules as OntoGuard-compatible action rules."""
        for rule in self.ontology.business_rules:
            self._add_business_rule(rule)

    def _add_business_rule(self, rule: BusinessRule):
        """Add a single business rule as an action rule."""
        safe_name = self._safe_name(rule.name)

        # Create rule class
        rule_class = self.ont[f"{safe_name}Rule"]
        self.graph.add((rule_class, RDF.type, OWL.Class))
        self.graph.add((rule_class, RDFS.subClassOf, self.ont.Action))
        self.graph.add((rule_class, RDFS.label, Literal(rule.name)))
        if rule.description:
            self.graph.add((rule_class, RDFS.comment, Literal(rule.description)))

        # Create rule instance
        rule_instance = self.ont[f"{safe_name}RuleInstance"]
        self.graph.add((rule_instance, RDF.type, rule_class))

        # Link to entity
        if rule.entity:
            entity_uri = self.ont[self._safe_name(rule.entity)]
            self.graph.add((rule_instance, self.ont.appliesTo, entity_uri))

        # Add condition as annotation
        if rule.condition:
            self.graph.add((rule_instance, self.ont.condition, Literal(rule.condition)))

        # Add action as annotation
        if rule.action:
            self.graph.add((rule_instance, self.ont.ruleAction, Literal(rule.action)))

        # Add classification
        if rule.classification:
            self.graph.add((rule_instance, self.ont.classification, Literal(rule.classification)))

        # Add priority
        self.graph.add((rule_instance, self.ont.priority, Literal(rule.priority, datatype=XSD.integer)))

        # Add source measure annotation
        if rule.source_measure:
            self.graph.add((rule_instance, self.ont.sourceMeasure, Literal(rule.source_measure)))

    def _add_default_crud_actions(self):
        """Add default CRUD action rules for each entity."""
        actions = ["read", "create", "update", "delete"]
        action_class_map = {
            "read": self.ont.ReadAction,
            "create": self.ont.WriteAction,
            "update": self.ont.WriteAction,
            "delete": self.ont.DeleteAction,
        }

        for entity in self.ontology.entities:
            entity_uri = self.ont[self._safe_name(entity.name)]

            for action in actions:
                for role in self.default_roles:
                    # Create action rule instance
                    action_name = f"{action}_{self._safe_name(entity.name)}_{self._safe_name(role)}"
                    action_uri = self.ont[action_name]
                    role_uri = self.ont[self._safe_name(role)]

                    self.graph.add((action_uri, RDF.type, action_class_map[action]))
                    self.graph.add((action_uri, self.ont.appliesTo, entity_uri))
                    self.graph.add((action_uri, self.ont.requiresRole, role_uri))
                    self.graph.add((action_uri, self.ont.allowsAction, Literal(action)))

    def add_rls_rules(self, security_rules: list):
        """
        Add Row-Level Security rules as OWL restrictions.

        Args:
            security_rules: List of SecurityRule objects from SemanticModel
        """
        # Create RLS-specific properties
        dax_filter_prop = self.ont.daxFilter
        self.graph.add((dax_filter_prop, RDF.type, OWL.DatatypeProperty))
        self.graph.add((dax_filter_prop, RDFS.label, Literal("daxFilter")))
        self.graph.add((dax_filter_prop, RDFS.comment, Literal("DAX filter expression for RLS")))

        for rule in security_rules:
            # Create role as User subclass if not exists
            role_uri = self.ont[self._safe_name(rule.role)]
            if (role_uri, RDF.type, OWL.Class) not in self.graph:
                self.graph.add((role_uri, RDF.type, OWL.Class))
                self.graph.add((role_uri, RDFS.subClassOf, self.ont.User))
                self.graph.add((role_uri, RDFS.label, Literal(rule.role)))

            # Create RLS action rule
            rls_name = f"RLS_{self._safe_name(rule.role)}_{self._safe_name(rule.table)}"
            rls_uri = self.ont[rls_name]

            self.graph.add((rls_uri, RDF.type, self.ont.ReadAction))
            self.graph.add((rls_uri, RDFS.label, Literal(f"RLS: {rule.role} on {rule.table}")))

            # Link to entity
            entity_uri = self.ont[self._safe_name(rule.table)]
            self.graph.add((rls_uri, self.ont.appliesTo, entity_uri))

            # Link to role
            self.graph.add((rls_uri, self.ont.requiresRole, role_uri))

            # Add DAX filter
            self.graph.add((rls_uri, dax_filter_prop, Literal(rule.dax_filter)))

            # Add description
            if hasattr(rule, 'description') and rule.description:
                self.graph.add((rls_uri, RDFS.comment, Literal(rule.description)))

            # Mark as RLS rule
            self.graph.add((rls_uri, self.ont.isRLSRule, Literal(True, datatype=XSD.boolean)))

    def _map_to_xsd(self, data_type: str) -> URIRef:
        """Map ontology data type to XSD type."""
        type_mapping = {
            "String": XSD.string,
            "Integer": XSD.integer,
            "Decimal": XSD.decimal,
            "Date": XSD.date,
            "DateTime": XSD.dateTime,
            "Boolean": XSD.boolean,
            "Float": XSD.float,
            "Double": XSD.double,
            "Long": XSD.long,
            "Binary": XSD.base64Binary,
        }
        return type_mapping.get(data_type, XSD.string)

    def _safe_name(self, name: str) -> str:
        """Convert name to URI-safe format."""
        if not name:
            return "unnamed"
        return name.replace(" ", "_").replace("-", "_").replace(".", "_")

    def save(self, filepath: str, format: str = "xml"):
        """
        Save OWL export to file.

        Args:
            filepath: Path to save file
            format: Output format
        """
        output = self.export(format=format)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output)
        logger.info(f"Saved OWL export to {filepath}")

    def get_export_summary(self) -> dict:
        """
        Get summary of exported OWL content.

        Returns:
            Dictionary with export statistics
        """
        # Export first to populate graph
        self.export()

        # Count classes
        classes = len(list(self.graph.subjects(RDF.type, OWL.Class)))

        # Count datatype properties
        datatype_props = len(list(self.graph.subjects(RDF.type, OWL.DatatypeProperty)))

        # Count object properties
        object_props = len(list(self.graph.subjects(RDF.type, OWL.ObjectProperty)))

        # Count action rules (instances of Action subclasses)
        action_rules = 0
        for action_type in ["ReadAction", "WriteAction", "DeleteAction", "ExecuteAction"]:
            action_rules += len(list(self.graph.subjects(RDF.type, self.ont[action_type])))

        return {
            "ontology_name": self.ontology.name,
            "total_triples": len(self.graph),
            "classes": classes,
            "datatype_properties": datatype_props,
            "object_properties": object_props,
            "entities": len(self.ontology.entities),
            "relationships": len(self.ontology.relationships),
            "business_rules": len(self.ontology.business_rules),
            "action_rules": action_rules,
            "default_roles": self.default_roles,
        }
