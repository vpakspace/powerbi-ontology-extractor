"""
Semantic Contract → OWL Converter

Converts SemanticContract to OntoGuard-compatible OWL format.
This enables AI agent contracts to be validated by OntoGuard semantic firewall.

Key mappings:
- read_entities → ReadAction with requiresRole/appliesTo
- write_properties → WriteAction with requiresRole/appliesTo
- executable_actions → ExecuteAction with requiresRole/appliesTo
- business_rules → Action classes with constraints
- context_filters → OWL restrictions
"""

import logging
from typing import Optional, Any

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD

logger = logging.getLogger(__name__)


class ContractToOWLConverter:
    """
    Converts SemanticContract to OntoGuard-compatible OWL format.

    This generates OWL action rules that can be loaded by OntoGuard
    for validating AI agent actions against their contract.

    Example:
        from powerbi_ontology.contract_builder import ContractBuilder, SemanticContract

        contract = builder.build_contract("SalesAgent", permissions)
        converter = ContractToOWLConverter(contract)
        converter.save("sales_agent_contract.owl")
    """

    def __init__(
        self,
        contract: Any,  # SemanticContract
        base_uri: Optional[str] = None,
        ontology: Optional[Any] = None  # Ontology for entity details
    ):
        """
        Initialize converter.

        Args:
            contract: SemanticContract to convert
            base_uri: Optional base URI (defaults to agent name)
            ontology: Optional Ontology for additional entity details
        """
        self.contract = contract
        self.ontology = ontology
        self.graph = Graph()

        # Create namespace
        agent_name = contract.agent_name.replace(" ", "_").replace("-", "_")
        self.base_uri = base_uri or f"http://example.org/contracts/{agent_name}#"

        self.ont = Namespace(self.base_uri)

        # Bind namespaces
        self.graph.bind("ont", self.ont)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("xsd", XSD)

    def convert(self, format: str = "xml") -> str:
        """
        Convert SemanticContract to OWL format.

        Args:
            format: Output format ("xml", "turtle", "json-ld", "n3")

        Returns:
            OWL content as string
        """
        logger.info(f"Converting contract '{self.contract.agent_name}' to OWL")

        # Add ontology metadata
        self._add_ontology_metadata()

        # Add base classes
        self._add_base_classes()

        # Add OntoGuard properties
        self._add_ontoguard_properties()

        # Add entity classes from permissions
        self._add_entity_classes()

        # Convert read permissions to action rules
        self._add_read_permissions()

        # Convert write permissions to action rules
        self._add_write_permissions()

        # Convert executable actions
        self._add_executable_actions()

        # Convert business rules
        self._add_business_rules()

        # Add context filters as restrictions
        self._add_context_filters()

        # Add audit configuration
        self._add_audit_config()

        return self.graph.serialize(format=format)

    def _add_ontology_metadata(self):
        """Add OWL ontology metadata."""
        ontology_uri = URIRef(self.base_uri.rstrip("#"))

        self.graph.add((ontology_uri, RDF.type, OWL.Ontology))
        self.graph.add((ontology_uri, RDFS.label, Literal(
            f"Contract: {self.contract.agent_name}"
        )))
        self.graph.add((ontology_uri, RDFS.comment, Literal(
            f"Semantic contract for AI agent '{self.contract.agent_name}'"
        )))
        self.graph.add((ontology_uri, OWL.versionInfo, Literal(
            self.contract.ontology_version
        )))

        # Add metadata
        metadata = self.contract.metadata or {}
        if metadata.get("created_date"):
            self.graph.add((ontology_uri, self.ont.createdDate, Literal(
                metadata["created_date"], datatype=XSD.dateTime
            )))
        if metadata.get("ontology_source"):
            self.graph.add((ontology_uri, self.ont.ontologySource, Literal(
                metadata["ontology_source"]
            )))

    def _add_base_classes(self):
        """Add base classes for OntoGuard compatibility."""
        # User/Role class
        user_uri = self.ont.User
        self.graph.add((user_uri, RDF.type, OWL.Class))
        self.graph.add((user_uri, RDFS.label, Literal("User")))

        # Add the agent's required role
        role = self.contract.permissions.required_role or "Agent"
        role_uri = self.ont[self._safe_name(role)]
        self.graph.add((role_uri, RDF.type, OWL.Class))
        self.graph.add((role_uri, RDFS.subClassOf, user_uri))
        self.graph.add((role_uri, RDFS.label, Literal(role)))
        self.graph.add((role_uri, RDFS.comment, Literal(
            f"Role required by agent {self.contract.agent_name}"
        )))

        # Action base class
        action_uri = self.ont.Action
        self.graph.add((action_uri, RDF.type, OWL.Class))
        self.graph.add((action_uri, RDFS.label, Literal("Action")))

        # Action subclasses
        for action_type in ["ReadAction", "WriteAction", "DeleteAction", "ExecuteAction"]:
            action_class = self.ont[action_type]
            self.graph.add((action_class, RDF.type, OWL.Class))
            self.graph.add((action_class, RDFS.subClassOf, action_uri))
            self.graph.add((action_class, RDFS.label, Literal(action_type)))

    def _add_ontoguard_properties(self):
        """Add OntoGuard action permission properties."""
        # requiresRole
        requires_role = self.ont.requiresRole
        self.graph.add((requires_role, RDF.type, OWL.ObjectProperty))
        self.graph.add((requires_role, RDFS.label, Literal("requires role")))
        self.graph.add((requires_role, RDFS.domain, self.ont.Action))
        self.graph.add((requires_role, RDFS.range, self.ont.User))

        # appliesTo
        applies_to = self.ont.appliesTo
        self.graph.add((applies_to, RDF.type, OWL.ObjectProperty))
        self.graph.add((applies_to, RDFS.label, Literal("applies to")))
        self.graph.add((applies_to, RDFS.domain, self.ont.Action))
        self.graph.add((applies_to, RDFS.range, OWL.Thing))

        # allowsAction
        allows_action = self.ont.allowsAction
        self.graph.add((allows_action, RDF.type, OWL.DatatypeProperty))
        self.graph.add((allows_action, RDFS.label, Literal("allows action")))
        self.graph.add((allows_action, RDFS.domain, self.ont.Action))
        self.graph.add((allows_action, RDFS.range, XSD.string))

        # appliesToProperty (for write permissions)
        applies_to_prop = self.ont.appliesToProperty
        self.graph.add((applies_to_prop, RDF.type, OWL.DatatypeProperty))
        self.graph.add((applies_to_prop, RDFS.label, Literal("applies to property")))
        self.graph.add((applies_to_prop, RDFS.domain, self.ont.Action))
        self.graph.add((applies_to_prop, RDFS.range, XSD.string))

        # hasContextFilter
        has_filter = self.ont.hasContextFilter
        self.graph.add((has_filter, RDF.type, OWL.DatatypeProperty))
        self.graph.add((has_filter, RDFS.label, Literal("has context filter")))
        self.graph.add((has_filter, RDFS.domain, self.ont.Action))
        self.graph.add((has_filter, RDFS.range, XSD.string))

    def _add_entity_classes(self):
        """Add entity classes from permissions."""
        # Collect all entities from permissions
        entities = set(self.contract.permissions.read_entities)
        entities.update(self.contract.permissions.write_properties.keys())

        for entity_name in entities:
            entity_uri = self.ont[self._safe_name(entity_name)]
            self.graph.add((entity_uri, RDF.type, OWL.Class))
            self.graph.add((entity_uri, RDFS.label, Literal(entity_name)))

            # If we have the ontology, add more details
            if self.ontology:
                ont_entity = next(
                    (e for e in self.ontology.entities if e.name == entity_name),
                    None
                )
                if ont_entity and ont_entity.description:
                    self.graph.add((entity_uri, RDFS.comment, Literal(ont_entity.description)))

    def _add_read_permissions(self):
        """Convert read_entities to ReadAction rules."""
        role = self.contract.permissions.required_role or "Agent"
        role_uri = self.ont[self._safe_name(role)]

        for entity_name in self.contract.permissions.read_entities:
            entity_uri = self.ont[self._safe_name(entity_name)]

            # Create action individual
            action_name = f"read_{self._safe_name(entity_name)}"
            action_uri = self.ont[action_name]

            self.graph.add((action_uri, RDF.type, self.ont.ReadAction))
            self.graph.add((action_uri, RDFS.label, Literal(f"Read {entity_name}")))
            self.graph.add((action_uri, self.ont.allowsAction, Literal("read")))
            self.graph.add((action_uri, self.ont.appliesTo, entity_uri))
            self.graph.add((action_uri, self.ont.requiresRole, role_uri))

            # Add context filter if exists
            context_filter = self.contract.permissions.context_filters.get(entity_name)
            if context_filter:
                self.graph.add((action_uri, self.ont.hasContextFilter, Literal(context_filter)))

    def _add_write_permissions(self):
        """Convert write_properties to WriteAction rules."""
        role = self.contract.permissions.required_role or "Agent"
        role_uri = self.ont[self._safe_name(role)]

        for entity_name, properties in self.contract.permissions.write_properties.items():
            entity_uri = self.ont[self._safe_name(entity_name)]

            # Create write action for each property
            for prop_name in properties:
                action_name = f"write_{self._safe_name(entity_name)}_{self._safe_name(prop_name)}"
                action_uri = self.ont[action_name]

                self.graph.add((action_uri, RDF.type, self.ont.WriteAction))
                self.graph.add((action_uri, RDFS.label, Literal(f"Write {entity_name}.{prop_name}")))
                self.graph.add((action_uri, self.ont.allowsAction, Literal("write")))
                self.graph.add((action_uri, self.ont.appliesTo, entity_uri))
                self.graph.add((action_uri, self.ont.appliesToProperty, Literal(prop_name)))
                self.graph.add((action_uri, self.ont.requiresRole, role_uri))

            # Also create general update action for entity
            update_action_name = f"update_{self._safe_name(entity_name)}"
            update_action_uri = self.ont[update_action_name]

            self.graph.add((update_action_uri, RDF.type, self.ont.WriteAction))
            self.graph.add((update_action_uri, RDFS.label, Literal(f"Update {entity_name}")))
            self.graph.add((update_action_uri, self.ont.allowsAction, Literal("update")))
            self.graph.add((update_action_uri, self.ont.appliesTo, entity_uri))
            self.graph.add((update_action_uri, self.ont.requiresRole, role_uri))

    def _add_executable_actions(self):
        """Convert executable_actions to ExecuteAction rules."""
        role = self.contract.permissions.required_role or "Agent"
        role_uri = self.ont[self._safe_name(role)]

        for action_name in self.contract.permissions.executable_actions:
            safe_action = self._safe_name(action_name)

            # Create action class
            action_class_uri = self.ont[f"{safe_action}Action"]
            self.graph.add((action_class_uri, RDF.type, OWL.Class))
            self.graph.add((action_class_uri, RDFS.subClassOf, self.ont.ExecuteAction))
            self.graph.add((action_class_uri, RDFS.label, Literal(action_name)))

            # Create action individual
            action_uri = self.ont[f"execute_{safe_action}"]
            self.graph.add((action_uri, RDF.type, action_class_uri))
            self.graph.add((action_uri, RDFS.label, Literal(f"Execute {action_name}")))
            self.graph.add((action_uri, self.ont.allowsAction, Literal("execute")))
            self.graph.add((action_uri, self.ont.requiresRole, role_uri))

    def _add_business_rules(self):
        """Convert business rules to OWL action rules."""
        for rule in self.contract.business_rules:
            safe_name = self._safe_name(rule.name)

            # Create action class for the rule
            rule_class_uri = self.ont[f"{safe_name}Rule"]
            self.graph.add((rule_class_uri, RDF.type, OWL.Class))
            self.graph.add((rule_class_uri, RDFS.subClassOf, self.ont.Action))
            self.graph.add((rule_class_uri, RDFS.label, Literal(rule.name)))

            if rule.description:
                self.graph.add((rule_class_uri, RDFS.comment, Literal(rule.description)))

            # Create rule individual
            rule_uri = self.ont[f"{safe_name}RuleInstance"]
            self.graph.add((rule_uri, RDF.type, rule_class_uri))

            # Add entity (appliesTo)
            if rule.entity:
                entity_uri = self.ont[self._safe_name(rule.entity)]
                self.graph.add((rule_uri, self.ont.appliesTo, entity_uri))

            # Add condition as annotation
            if rule.condition:
                self.graph.add((rule_uri, self.ont.ruleCondition, Literal(rule.condition)))

            # Add action
            if rule.action:
                self.graph.add((rule_uri, self.ont.ruleAction, Literal(rule.action)))

            # Determine role from classification
            classification = getattr(rule, 'classification', 'low')
            if classification:
                role_map = {
                    'critical': 'Admin',
                    'high': 'Admin',
                    'medium': 'Editor',
                    'low': 'Viewer'
                }
                required_role = role_map.get(classification.lower(), 'Agent')
                self.graph.add((rule_uri, self.ont.requiresRole, self.ont[required_role]))

    def _add_context_filters(self):
        """Add context filters as OWL annotations."""
        for entity_name, filter_condition in self.contract.permissions.context_filters.items():
            entity_uri = self.ont[self._safe_name(entity_name)]

            # Add filter as annotation
            self.graph.add((entity_uri, self.ont.contextFilter, Literal(filter_condition)))

    def _add_audit_config(self):
        """Add audit configuration as annotations."""
        ontology_uri = URIRef(self.base_uri.rstrip("#"))
        audit = self.contract.audit_settings

        self.graph.add((ontology_uri, self.ont.auditLogReads, Literal(
            audit.log_reads, datatype=XSD.boolean
        )))
        self.graph.add((ontology_uri, self.ont.auditLogWrites, Literal(
            audit.log_writes, datatype=XSD.boolean
        )))
        self.graph.add((ontology_uri, self.ont.auditLogActions, Literal(
            audit.log_actions, datatype=XSD.boolean
        )))
        self.graph.add((ontology_uri, self.ont.alertOnViolation, Literal(
            audit.alert_on_violation, datatype=XSD.boolean
        )))

    def _safe_name(self, name: str) -> str:
        """Convert name to valid URI component."""
        safe = name.replace(" ", "_").replace("-", "_").replace(".", "_")
        safe = "".join(c for c in safe if c.isalnum() or c == "_")
        return safe

    def save(self, filepath: str, format: str = "xml"):
        """
        Save OWL export to file.

        Args:
            filepath: Path to save file
            format: Output format
        """
        output = self.convert(format=format)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(output)
        logger.info(f"Saved contract OWL to {filepath}")

    def get_action_rules_summary(self) -> dict:
        """
        Get summary of generated action rules.

        Returns:
            Dictionary with counts of different rule types
        """
        self.convert()  # Ensure graph is populated

        read_actions = len(list(self.graph.subjects(RDF.type, self.ont.ReadAction)))
        write_actions = len(list(self.graph.subjects(RDF.type, self.ont.WriteAction)))
        execute_actions = len(list(self.graph.subjects(RDF.type, self.ont.ExecuteAction)))

        return {
            "agent_name": self.contract.agent_name,
            "required_role": self.contract.permissions.required_role,
            "read_actions": read_actions,
            "write_actions": write_actions,
            "execute_actions": execute_actions,
            "business_rules": len(self.contract.business_rules),
            "total_triples": len(self.graph)
        }
