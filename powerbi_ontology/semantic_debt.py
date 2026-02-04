"""
Semantic Debt Analysis for Multi-Dashboard Environments.

Detects conflicting definitions across multiple Power BI dashboards:
- Measures with same name but different DAX formulas
- Properties with same name but different data types
- Entities with same name but different structures
- Conflicting business rules
- Incompatible relationships

Use case: "Revenue" defined differently in Sales.pbix vs Finance.pbix
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Tuple
from difflib import SequenceMatcher

from powerbi_ontology.ontology_generator import (
    Ontology,
    OntologyEntity,
    OntologyProperty,
    OntologyRelationship,
    BusinessRule,
)

logger = logging.getLogger(__name__)


class ConflictSeverity(Enum):
    """Severity levels for semantic conflicts."""
    CRITICAL = "critical"  # Completely different definitions, will cause errors
    WARNING = "warning"    # Partial differences, needs attention
    INFO = "info"          # Minor differences, can be ignored


class ConflictType(Enum):
    """Types of semantic conflicts."""
    MEASURE_CONFLICT = "measure_conflict"           # Same measure name, different DAX
    TYPE_CONFLICT = "type_conflict"                 # Same property name, different type
    ENTITY_CONFLICT = "entity_conflict"             # Same entity name, different structure
    RELATIONSHIP_CONFLICT = "relationship_conflict" # Different relationship between same entities
    RULE_CONFLICT = "rule_conflict"                 # Conflicting business rules


@dataclass
class SemanticConflict:
    """Represents a semantic conflict between dashboards."""
    conflict_type: ConflictType
    severity: ConflictSeverity
    name: str                           # Name of conflicting element
    sources: List[str]                  # List of source files/ontologies
    details: Dict[str, str]             # Details per source
    description: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "conflict_type": self.conflict_type.value,
            "severity": self.severity.value,
            "name": self.name,
            "sources": self.sources,
            "details": self.details,
            "description": self.description,
            "recommendation": self.recommendation,
        }


@dataclass
class SemanticDebtReport:
    """Report of semantic debt analysis."""
    ontologies_analyzed: List[str]
    conflicts: List[SemanticConflict] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

    def add_conflict(self, conflict: SemanticConflict):
        """Add a conflict to the report."""
        self.conflicts.append(conflict)

    def generate_summary(self):
        """Generate summary statistics."""
        self.summary = {
            "total_conflicts": len(self.conflicts),
            "critical": sum(1 for c in self.conflicts if c.severity == ConflictSeverity.CRITICAL),
            "warning": sum(1 for c in self.conflicts if c.severity == ConflictSeverity.WARNING),
            "info": sum(1 for c in self.conflicts if c.severity == ConflictSeverity.INFO),
            "by_type": {},
        }

        for conflict_type in ConflictType:
            count = sum(1 for c in self.conflicts if c.conflict_type == conflict_type)
            if count > 0:
                self.summary["by_type"][conflict_type.value] = count

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        self.generate_summary()
        return {
            "ontologies_analyzed": self.ontologies_analyzed,
            "summary": self.summary,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        self.generate_summary()

        lines = [
            "# Semantic Debt Analysis Report",
            "",
            "## Summary",
            "",
            f"- **Ontologies analyzed:** {len(self.ontologies_analyzed)}",
            f"- **Total conflicts:** {self.summary['total_conflicts']}",
            f"  - 🔴 Critical: {self.summary['critical']}",
            f"  - 🟡 Warning: {self.summary['warning']}",
            f"  - 🔵 Info: {self.summary['info']}",
            "",
        ]

        if self.summary.get("by_type"):
            lines.append("### Conflicts by Type")
            lines.append("")
            for ctype, count in self.summary["by_type"].items():
                lines.append(f"- {ctype}: {count}")
            lines.append("")

        # Critical conflicts first
        critical = [c for c in self.conflicts if c.severity == ConflictSeverity.CRITICAL]
        if critical:
            lines.append("## 🔴 Critical Conflicts")
            lines.append("")
            for c in critical:
                lines.extend(self._format_conflict(c))

        # Warning conflicts
        warnings = [c for c in self.conflicts if c.severity == ConflictSeverity.WARNING]
        if warnings:
            lines.append("## 🟡 Warnings")
            lines.append("")
            for c in warnings:
                lines.extend(self._format_conflict(c))

        # Info conflicts
        infos = [c for c in self.conflicts if c.severity == ConflictSeverity.INFO]
        if infos:
            lines.append("## 🔵 Info")
            lines.append("")
            for c in infos:
                lines.extend(self._format_conflict(c))

        # Recommendations
        if self.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        return "\n".join(lines)

    def _format_conflict(self, conflict: SemanticConflict) -> List[str]:
        """Format a single conflict for markdown."""
        lines = [
            f"### {conflict.name}",
            "",
            f"**Type:** {conflict.conflict_type.value}",
            "",
            f"**Description:** {conflict.description}",
            "",
            "**Sources:**",
            "",
        ]

        for source, detail in conflict.details.items():
            lines.append(f"- `{source}`: {detail}")

        lines.append("")

        if conflict.recommendation:
            lines.append(f"**Recommendation:** {conflict.recommendation}")
            lines.append("")

        return lines


class SemanticDebtAnalyzer:
    """
    Analyzes semantic debt across multiple ontologies.

    Detects conflicting definitions that could cause inconsistencies
    when AI agents work across multiple Power BI dashboards.
    """

    def __init__(self, similarity_threshold: float = 0.8):
        """
        Initialize analyzer.

        Args:
            similarity_threshold: Threshold for name similarity matching (0-1)
        """
        self.similarity_threshold = similarity_threshold
        self.ontologies: Dict[str, Ontology] = {}

    def add_ontology(self, name: str, ontology: Ontology):
        """
        Add an ontology for analysis.

        Args:
            name: Identifier for this ontology (e.g., filename)
            ontology: Ontology object
        """
        self.ontologies[name] = ontology
        logger.info(f"Added ontology '{name}' with {len(ontology.entities)} entities")

    def load_ontologies_from_directory(self, directory: str, pattern: str = "*.json"):
        """
        Load multiple ontologies from a directory.

        Args:
            directory: Directory path
            pattern: Glob pattern for files
        """
        import json
        from pathlib import Path

        dir_path = Path(directory)
        for file_path in dir_path.glob(pattern):
            try:
                with open(file_path) as f:
                    data = json.load(f)

                # Simple conversion - assumes same format as ontology_editor.py
                ontology = self._json_to_ontology(data)
                self.add_ontology(file_path.name, ontology)
            except Exception as e:
                logger.warning(f"Failed to load {file_path}: {e}")

    def _json_to_ontology(self, data: dict) -> Ontology:
        """Convert JSON data to Ontology object."""
        from powerbi_ontology.ontology_generator import Constraint

        entities = []
        for e_data in data.get("entities", []):
            props = []
            for p_data in e_data.get("properties", []):
                constraints = [
                    Constraint(type=c["type"], value=c["value"], message=c.get("message", ""))
                    for c in p_data.get("constraints", [])
                ]
                props.append(OntologyProperty(
                    name=p_data["name"],
                    data_type=p_data.get("data_type", "String"),
                    required=p_data.get("required", False),
                    unique=p_data.get("unique", False),
                    description=p_data.get("description", ""),
                    constraints=constraints,
                ))

            entities.append(OntologyEntity(
                name=e_data["name"],
                description=e_data.get("description", ""),
                entity_type=e_data.get("entity_type", "standard"),
                properties=props,
                constraints=[],
            ))

        relationships = []
        for r_data in data.get("relationships", []):
            relationships.append(OntologyRelationship(
                from_entity=r_data["from_entity"],
                to_entity=r_data["to_entity"],
                from_property=r_data.get("from_property", ""),
                to_property=r_data.get("to_property", ""),
                relationship_type=r_data.get("relationship_type", "related_to"),
                cardinality=r_data.get("cardinality", "one-to-many"),
                description=r_data.get("description", ""),
            ))

        rules = []
        for b_data in data.get("business_rules", []):
            rules.append(BusinessRule(
                name=b_data["name"],
                entity=b_data.get("entity", ""),
                condition=b_data.get("condition", ""),
                action=b_data.get("action", ""),
                classification=b_data.get("classification", ""),
                description=b_data.get("description", ""),
                priority=b_data.get("priority", 1),
            ))

        return Ontology(
            name=data.get("name", "Unnamed"),
            version=data.get("version", "1.0"),
            source=data.get("source", ""),
            entities=entities,
            relationships=relationships,
            business_rules=rules,
            metadata=data.get("metadata", {}),
        )

    def analyze(self) -> SemanticDebtReport:
        """
        Perform semantic debt analysis.

        Returns:
            SemanticDebtReport with all detected conflicts
        """
        if len(self.ontologies) < 2:
            logger.warning("Need at least 2 ontologies for comparison")
            return SemanticDebtReport(
                ontologies_analyzed=list(self.ontologies.keys()),
                conflicts=[],
            )

        report = SemanticDebtReport(ontologies_analyzed=list(self.ontologies.keys()))

        # Analyze different conflict types
        self._analyze_entity_conflicts(report)
        self._analyze_property_type_conflicts(report)
        self._analyze_relationship_conflicts(report)
        self._analyze_business_rule_conflicts(report)

        # Generate recommendations
        self._generate_recommendations(report)

        report.generate_summary()
        return report

    def _analyze_entity_conflicts(self, report: SemanticDebtReport):
        """Detect entities with same name but different structures."""
        entity_map: Dict[str, Dict[str, OntologyEntity]] = {}

        # Group entities by name
        for ont_name, ont in self.ontologies.items():
            for entity in ont.entities:
                if entity.name not in entity_map:
                    entity_map[entity.name] = {}
                entity_map[entity.name][ont_name] = entity

        # Check for conflicts
        for entity_name, sources in entity_map.items():
            if len(sources) < 2:
                continue

            # Compare property sets
            source_names = list(sources.keys())
            for i in range(len(source_names)):
                for j in range(i + 1, len(source_names)):
                    src1, src2 = source_names[i], source_names[j]
                    entity1, entity2 = sources[src1], sources[src2]

                    props1 = set(p.name for p in entity1.properties)
                    props2 = set(p.name for p in entity2.properties)

                    # Check for structural differences
                    only_in_1 = props1 - props2
                    only_in_2 = props2 - props1

                    if only_in_1 or only_in_2:
                        severity = self._determine_entity_severity(entity1, entity2)

                        details = {
                            src1: f"Properties: {', '.join(sorted(props1))}",
                            src2: f"Properties: {', '.join(sorted(props2))}",
                        }

                        missing_desc = []
                        if only_in_1:
                            missing_desc.append(f"only in {src1}: {', '.join(sorted(only_in_1))}")
                        if only_in_2:
                            missing_desc.append(f"only in {src2}: {', '.join(sorted(only_in_2))}")

                        report.add_conflict(SemanticConflict(
                            conflict_type=ConflictType.ENTITY_CONFLICT,
                            severity=severity,
                            name=entity_name,
                            sources=[src1, src2],
                            details=details,
                            description=f"Entity '{entity_name}' has different structures: {'; '.join(missing_desc)}",
                            recommendation=f"Unify entity '{entity_name}' structure across dashboards or rename to avoid confusion.",
                        ))

    def _analyze_property_type_conflicts(self, report: SemanticDebtReport):
        """Detect properties with same name but different types."""
        # Group properties by (entity_name, property_name)
        prop_map: Dict[Tuple[str, str], Dict[str, OntologyProperty]] = {}

        for ont_name, ont in self.ontologies.items():
            for entity in ont.entities:
                for prop in entity.properties:
                    key = (entity.name, prop.name)
                    if key not in prop_map:
                        prop_map[key] = {}
                    prop_map[key][ont_name] = prop

        # Check for type conflicts
        for (entity_name, prop_name), sources in prop_map.items():
            if len(sources) < 2:
                continue

            types = {src: prop.data_type for src, prop in sources.items()}
            unique_types = set(types.values())

            if len(unique_types) > 1:
                severity = ConflictSeverity.CRITICAL

                details = {src: f"Type: {t}" for src, t in types.items()}

                report.add_conflict(SemanticConflict(
                    conflict_type=ConflictType.TYPE_CONFLICT,
                    severity=severity,
                    name=f"{entity_name}.{prop_name}",
                    sources=list(sources.keys()),
                    details=details,
                    description=f"Property '{entity_name}.{prop_name}' has different types: {', '.join(unique_types)}",
                    recommendation=f"Standardize the data type for '{prop_name}' across all dashboards.",
                ))

    def _analyze_relationship_conflicts(self, report: SemanticDebtReport):
        """Detect conflicting relationships between same entities."""
        # Group relationships by (from_entity, to_entity)
        rel_map: Dict[Tuple[str, str], Dict[str, OntologyRelationship]] = {}

        for ont_name, ont in self.ontologies.items():
            for rel in ont.relationships:
                key = (rel.from_entity, rel.to_entity)
                if key not in rel_map:
                    rel_map[key] = {}
                rel_map[key][ont_name] = rel

        # Check for conflicts
        for (from_ent, to_ent), sources in rel_map.items():
            if len(sources) < 2:
                continue

            cardinalities = {src: rel.cardinality for src, rel in sources.items()}
            unique_cards = set(cardinalities.values())

            if len(unique_cards) > 1:
                severity = ConflictSeverity.WARNING

                details = {
                    src: f"Type: {rel.relationship_type}, Cardinality: {rel.cardinality}"
                    for src, rel in sources.items()
                }

                report.add_conflict(SemanticConflict(
                    conflict_type=ConflictType.RELATIONSHIP_CONFLICT,
                    severity=severity,
                    name=f"{from_ent} → {to_ent}",
                    sources=list(sources.keys()),
                    details=details,
                    description=f"Relationship '{from_ent} → {to_ent}' has different cardinalities: {', '.join(unique_cards)}",
                    recommendation="Verify the correct cardinality and update dashboards accordingly.",
                ))

    def _analyze_business_rule_conflicts(self, report: SemanticDebtReport):
        """Detect conflicting business rules."""
        # Group rules by name
        rule_map: Dict[str, Dict[str, BusinessRule]] = {}

        for ont_name, ont in self.ontologies.items():
            for rule in ont.business_rules:
                if rule.name not in rule_map:
                    rule_map[rule.name] = {}
                rule_map[rule.name][ont_name] = rule

        # Check for conflicts
        for rule_name, sources in rule_map.items():
            if len(sources) < 2:
                continue

            conditions = {src: rule.condition for src, rule in sources.items()}
            unique_conditions = set(conditions.values())

            if len(unique_conditions) > 1:
                # Check similarity
                conds_list = list(unique_conditions)
                similarity = self._text_similarity(conds_list[0], conds_list[1])

                if similarity < self.similarity_threshold:
                    severity = ConflictSeverity.CRITICAL
                else:
                    severity = ConflictSeverity.WARNING

                details = {
                    src: f"Condition: {rule.condition}, Action: {rule.action}"
                    for src, rule in sources.items()
                }

                report.add_conflict(SemanticConflict(
                    conflict_type=ConflictType.RULE_CONFLICT,
                    severity=severity,
                    name=rule_name,
                    sources=list(sources.keys()),
                    details=details,
                    description=f"Business rule '{rule_name}' has different conditions across dashboards.",
                    recommendation=f"Consolidate rule '{rule_name}' into a single source of truth.",
                ))

    def _determine_entity_severity(
        self, entity1: OntologyEntity, entity2: OntologyEntity
    ) -> ConflictSeverity:
        """Determine severity based on structural differences."""
        props1 = set(p.name for p in entity1.properties)
        props2 = set(p.name for p in entity2.properties)

        common = props1 & props2
        total = props1 | props2

        if not total:
            return ConflictSeverity.INFO

        overlap_ratio = len(common) / len(total)

        if overlap_ratio < 0.5:
            return ConflictSeverity.CRITICAL
        elif overlap_ratio < 0.8:
            return ConflictSeverity.WARNING
        else:
            return ConflictSeverity.INFO

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts."""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def _generate_recommendations(self, report: SemanticDebtReport):
        """Generate overall recommendations based on conflicts."""
        if not report.conflicts:
            report.recommendations.append("No semantic conflicts detected. Good job!")
            return

        critical_count = sum(1 for c in report.conflicts if c.severity == ConflictSeverity.CRITICAL)
        warning_count = sum(1 for c in report.conflicts if c.severity == ConflictSeverity.WARNING)

        if critical_count > 0:
            report.recommendations.append(
                f"Address {critical_count} critical conflict(s) immediately - they may cause data inconsistencies."
            )

        # Check for specific patterns
        type_conflicts = [c for c in report.conflicts if c.conflict_type == ConflictType.TYPE_CONFLICT]
        if type_conflicts:
            report.recommendations.append(
                "Create a shared data dictionary to standardize property types across dashboards."
            )

        entity_conflicts = [c for c in report.conflicts if c.conflict_type == ConflictType.ENTITY_CONFLICT]
        if entity_conflicts:
            report.recommendations.append(
                "Consider creating a master ontology schema that all dashboards inherit from."
            )

        rule_conflicts = [c for c in report.conflicts if c.conflict_type == ConflictType.RULE_CONFLICT]
        if rule_conflicts:
            report.recommendations.append(
                "Centralize business rules in a single repository to ensure consistency."
            )

        if warning_count > 3:
            report.recommendations.append(
                "Schedule a semantic alignment review with stakeholders from different dashboard teams."
            )


def analyze_ontologies(ontologies: Dict[str, Ontology]) -> SemanticDebtReport:
    """
    Convenience function to analyze multiple ontologies.

    Args:
        ontologies: Dictionary mapping names to Ontology objects

    Returns:
        SemanticDebtReport
    """
    analyzer = SemanticDebtAnalyzer()
    for name, ont in ontologies.items():
        analyzer.add_ontology(name, ont)
    return analyzer.analyze()
