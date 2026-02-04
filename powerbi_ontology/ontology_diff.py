"""
Ontology Diff Tool - Compare versions of ontologies.

Provides Git-like diff functionality for ontologies:
- Detect added, removed, modified elements
- Generate changelogs
- Support merge operations

Use case: Track changes between ontology versions or compare branches.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from difflib import unified_diff

from powerbi_ontology.ontology_generator import (
    Ontology,
    OntologyEntity,
    OntologyProperty,
    OntologyRelationship,
    BusinessRule,
)

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of changes between ontology versions."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


class ElementType(Enum):
    """Types of ontology elements."""
    ENTITY = "entity"
    PROPERTY = "property"
    RELATIONSHIP = "relationship"
    RULE = "rule"
    METADATA = "metadata"


@dataclass
class Change:
    """Represents a single change between ontology versions."""
    change_type: ChangeType
    element_type: ElementType
    element_name: str
    path: str  # Full path like "Entity.Property"
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    details: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "change_type": self.change_type.value,
            "element_type": self.element_type.value,
            "element_name": self.element_name,
            "path": self.path,
            "old_value": str(self.old_value) if self.old_value else None,
            "new_value": str(self.new_value) if self.new_value else None,
            "details": self.details,
        }


@dataclass
class DiffReport:
    """Report of differences between two ontology versions."""
    source_name: str
    target_name: str
    source_version: str
    target_version: str
    changes: List[Change] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def add_change(self, change: Change):
        """Add a change to the report."""
        self.changes.append(change)

    def generate_summary(self):
        """Generate summary statistics."""
        self.summary = {
            "total_changes": len(self.changes),
            "added": sum(1 for c in self.changes if c.change_type == ChangeType.ADDED),
            "removed": sum(1 for c in self.changes if c.change_type == ChangeType.REMOVED),
            "modified": sum(1 for c in self.changes if c.change_type == ChangeType.MODIFIED),
            "by_element": {},
        }

        for element_type in ElementType:
            count = sum(1 for c in self.changes if c.element_type == element_type)
            if count > 0:
                self.summary["by_element"][element_type.value] = count

    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return len(self.changes) > 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        self.generate_summary()
        return {
            "source": {"name": self.source_name, "version": self.source_version},
            "target": {"name": self.target_name, "version": self.target_version},
            "summary": self.summary,
            "changes": [c.to_dict() for c in self.changes],
        }

    def to_changelog(self) -> str:
        """Generate changelog in markdown format."""
        self.generate_summary()

        lines = [
            f"# Changelog: {self.source_name} → {self.target_name}",
            "",
            f"**From**: {self.source_name} v{self.source_version}",
            f"**To**: {self.target_name} v{self.target_version}",
            "",
            "## Summary",
            "",
            f"- Total changes: {self.summary['total_changes']}",
            f"- ➕ Added: {self.summary['added']}",
            f"- ➖ Removed: {self.summary['removed']}",
            f"- 📝 Modified: {self.summary['modified']}",
            "",
        ]

        # Group changes by element type
        added = [c for c in self.changes if c.change_type == ChangeType.ADDED]
        removed = [c for c in self.changes if c.change_type == ChangeType.REMOVED]
        modified = [c for c in self.changes if c.change_type == ChangeType.MODIFIED]

        if added:
            lines.append("## ➕ Added")
            lines.append("")
            for c in added:
                lines.append(f"- **{c.element_type.value}**: `{c.path}`")
                if c.details:
                    lines.append(f"  - {c.details}")
            lines.append("")

        if removed:
            lines.append("## ➖ Removed")
            lines.append("")
            for c in removed:
                lines.append(f"- **{c.element_type.value}**: `{c.path}`")
                if c.details:
                    lines.append(f"  - {c.details}")
            lines.append("")

        if modified:
            lines.append("## 📝 Modified")
            lines.append("")
            for c in modified:
                lines.append(f"- **{c.element_type.value}**: `{c.path}`")
                if c.old_value and c.new_value:
                    lines.append(f"  - Was: `{c.old_value}`")
                    lines.append(f"  - Now: `{c.new_value}`")
                if c.details:
                    lines.append(f"  - {c.details}")
            lines.append("")

        return "\n".join(lines)

    def to_unified_diff(self) -> str:
        """Generate unified diff format (like git diff)."""
        source_lines = self._ontology_to_lines("source")
        target_lines = self._ontology_to_lines("target")

        diff = unified_diff(
            source_lines,
            target_lines,
            fromfile=f"{self.source_name} v{self.source_version}",
            tofile=f"{self.target_name} v{self.target_version}",
            lineterm="",
        )
        return "\n".join(diff)

    def _ontology_to_lines(self, which: str) -> List[str]:
        """Convert changes to text lines for diff."""
        lines = []
        for c in self.changes:
            if which == "source" and c.old_value:
                lines.append(f"{c.element_type.value}: {c.path} = {c.old_value}")
            elif which == "target" and c.new_value:
                lines.append(f"{c.element_type.value}: {c.path} = {c.new_value}")
        return sorted(lines)


class OntologyDiff:
    """
    Compares two ontology versions and generates diff reports.

    Supports:
    - Entity comparison (added/removed/modified)
    - Property comparison within entities
    - Relationship comparison
    - Business rule comparison
    - Metadata comparison
    """

    def __init__(self, source: Ontology, target: Ontology):
        """
        Initialize diff tool.

        Args:
            source: Original/old ontology version
            target: New/updated ontology version
        """
        self.source = source
        self.target = target

    def diff(self) -> DiffReport:
        """
        Perform diff between source and target ontologies.

        Returns:
            DiffReport with all detected changes
        """
        report = DiffReport(
            source_name=self.source.name,
            target_name=self.target.name,
            source_version=self.source.version,
            target_version=self.target.version,
        )

        # Compare all elements
        self._diff_entities(report)
        self._diff_relationships(report)
        self._diff_business_rules(report)
        self._diff_metadata(report)

        report.generate_summary()
        return report

    def _diff_entities(self, report: DiffReport):
        """Compare entities between versions."""
        source_entities = {e.name: e for e in self.source.entities}
        target_entities = {e.name: e for e in self.target.entities}

        source_names = set(source_entities.keys())
        target_names = set(target_entities.keys())

        # Added entities
        for name in target_names - source_names:
            entity = target_entities[name]
            report.add_change(Change(
                change_type=ChangeType.ADDED,
                element_type=ElementType.ENTITY,
                element_name=name,
                path=name,
                new_value=f"type={entity.entity_type}, properties={len(entity.properties)}",
                details=entity.description or "",
            ))

        # Removed entities
        for name in source_names - target_names:
            entity = source_entities[name]
            report.add_change(Change(
                change_type=ChangeType.REMOVED,
                element_type=ElementType.ENTITY,
                element_name=name,
                path=name,
                old_value=f"type={entity.entity_type}, properties={len(entity.properties)}",
                details=entity.description or "",
            ))

        # Modified entities
        for name in source_names & target_names:
            self._diff_entity(report, source_entities[name], target_entities[name])

    def _diff_entity(self, report: DiffReport, source: OntologyEntity, target: OntologyEntity):
        """Compare a single entity between versions."""
        # Check entity type change
        if source.entity_type != target.entity_type:
            report.add_change(Change(
                change_type=ChangeType.MODIFIED,
                element_type=ElementType.ENTITY,
                element_name=source.name,
                path=f"{source.name}.entity_type",
                old_value=source.entity_type,
                new_value=target.entity_type,
                details="Entity type changed",
            ))

        # Check description change
        if source.description != target.description:
            report.add_change(Change(
                change_type=ChangeType.MODIFIED,
                element_type=ElementType.ENTITY,
                element_name=source.name,
                path=f"{source.name}.description",
                old_value=source.description,
                new_value=target.description,
                details="Description updated",
            ))

        # Compare properties
        self._diff_properties(report, source.name, source.properties, target.properties)

    def _diff_properties(
        self,
        report: DiffReport,
        entity_name: str,
        source_props: List[OntologyProperty],
        target_props: List[OntologyProperty],
    ):
        """Compare properties within an entity."""
        source_map = {p.name: p for p in source_props}
        target_map = {p.name: p for p in target_props}

        source_names = set(source_map.keys())
        target_names = set(target_map.keys())

        # Added properties
        for name in target_names - source_names:
            prop = target_map[name]
            report.add_change(Change(
                change_type=ChangeType.ADDED,
                element_type=ElementType.PROPERTY,
                element_name=name,
                path=f"{entity_name}.{name}",
                new_value=f"type={prop.data_type}, required={prop.required}",
                details=prop.description or "",
            ))

        # Removed properties
        for name in source_names - target_names:
            prop = source_map[name]
            report.add_change(Change(
                change_type=ChangeType.REMOVED,
                element_type=ElementType.PROPERTY,
                element_name=name,
                path=f"{entity_name}.{name}",
                old_value=f"type={prop.data_type}, required={prop.required}",
                details=prop.description or "",
            ))

        # Modified properties
        for name in source_names & target_names:
            self._diff_property(report, entity_name, source_map[name], target_map[name])

    def _diff_property(
        self,
        report: DiffReport,
        entity_name: str,
        source: OntologyProperty,
        target: OntologyProperty,
    ):
        """Compare a single property between versions."""
        path = f"{entity_name}.{source.name}"

        # Check data type
        if source.data_type != target.data_type:
            report.add_change(Change(
                change_type=ChangeType.MODIFIED,
                element_type=ElementType.PROPERTY,
                element_name=source.name,
                path=f"{path}.data_type",
                old_value=source.data_type,
                new_value=target.data_type,
                details="Data type changed",
            ))

        # Check required
        if source.required != target.required:
            report.add_change(Change(
                change_type=ChangeType.MODIFIED,
                element_type=ElementType.PROPERTY,
                element_name=source.name,
                path=f"{path}.required",
                old_value=str(source.required),
                new_value=str(target.required),
                details="Required flag changed",
            ))

        # Check unique
        if source.unique != target.unique:
            report.add_change(Change(
                change_type=ChangeType.MODIFIED,
                element_type=ElementType.PROPERTY,
                element_name=source.name,
                path=f"{path}.unique",
                old_value=str(source.unique),
                new_value=str(target.unique),
                details="Unique flag changed",
            ))

    def _diff_relationships(self, report: DiffReport):
        """Compare relationships between versions."""
        def rel_key(r: OntologyRelationship) -> str:
            return f"{r.from_entity}→{r.to_entity}"

        source_rels = {rel_key(r): r for r in self.source.relationships}
        target_rels = {rel_key(r): r for r in self.target.relationships}

        source_keys = set(source_rels.keys())
        target_keys = set(target_rels.keys())

        # Added relationships
        for key in target_keys - source_keys:
            rel = target_rels[key]
            report.add_change(Change(
                change_type=ChangeType.ADDED,
                element_type=ElementType.RELATIONSHIP,
                element_name=key,
                path=key,
                new_value=f"type={rel.relationship_type}, cardinality={rel.cardinality}",
                details=rel.description or "",
            ))

        # Removed relationships
        for key in source_keys - target_keys:
            rel = source_rels[key]
            report.add_change(Change(
                change_type=ChangeType.REMOVED,
                element_type=ElementType.RELATIONSHIP,
                element_name=key,
                path=key,
                old_value=f"type={rel.relationship_type}, cardinality={rel.cardinality}",
                details=rel.description or "",
            ))

        # Modified relationships
        for key in source_keys & target_keys:
            self._diff_relationship(report, source_rels[key], target_rels[key])

    def _diff_relationship(
        self,
        report: DiffReport,
        source: OntologyRelationship,
        target: OntologyRelationship,
    ):
        """Compare a single relationship between versions."""
        key = f"{source.from_entity}→{source.to_entity}"

        if source.relationship_type != target.relationship_type:
            report.add_change(Change(
                change_type=ChangeType.MODIFIED,
                element_type=ElementType.RELATIONSHIP,
                element_name=key,
                path=f"{key}.type",
                old_value=source.relationship_type,
                new_value=target.relationship_type,
                details="Relationship type changed",
            ))

        if source.cardinality != target.cardinality:
            report.add_change(Change(
                change_type=ChangeType.MODIFIED,
                element_type=ElementType.RELATIONSHIP,
                element_name=key,
                path=f"{key}.cardinality",
                old_value=source.cardinality,
                new_value=target.cardinality,
                details="Cardinality changed",
            ))

    def _diff_business_rules(self, report: DiffReport):
        """Compare business rules between versions."""
        source_rules = {r.name: r for r in self.source.business_rules}
        target_rules = {r.name: r for r in self.target.business_rules}

        source_names = set(source_rules.keys())
        target_names = set(target_rules.keys())

        # Added rules
        for name in target_names - source_names:
            rule = target_rules[name]
            report.add_change(Change(
                change_type=ChangeType.ADDED,
                element_type=ElementType.RULE,
                element_name=name,
                path=f"rule:{name}",
                new_value=f"condition={rule.condition}, action={rule.action}",
                details=rule.description or "",
            ))

        # Removed rules
        for name in source_names - target_names:
            rule = source_rules[name]
            report.add_change(Change(
                change_type=ChangeType.REMOVED,
                element_type=ElementType.RULE,
                element_name=name,
                path=f"rule:{name}",
                old_value=f"condition={rule.condition}, action={rule.action}",
                details=rule.description or "",
            ))

        # Modified rules
        for name in source_names & target_names:
            self._diff_rule(report, source_rules[name], target_rules[name])

    def _diff_rule(self, report: DiffReport, source: BusinessRule, target: BusinessRule):
        """Compare a single business rule between versions."""
        path = f"rule:{source.name}"

        if source.condition != target.condition:
            report.add_change(Change(
                change_type=ChangeType.MODIFIED,
                element_type=ElementType.RULE,
                element_name=source.name,
                path=f"{path}.condition",
                old_value=source.condition,
                new_value=target.condition,
                details="Condition changed",
            ))

        if source.action != target.action:
            report.add_change(Change(
                change_type=ChangeType.MODIFIED,
                element_type=ElementType.RULE,
                element_name=source.name,
                path=f"{path}.action",
                old_value=source.action,
                new_value=target.action,
                details="Action changed",
            ))

        if source.classification != target.classification:
            report.add_change(Change(
                change_type=ChangeType.MODIFIED,
                element_type=ElementType.RULE,
                element_name=source.name,
                path=f"{path}.classification",
                old_value=source.classification,
                new_value=target.classification,
                details="Classification changed",
            ))

    def _diff_metadata(self, report: DiffReport):
        """Compare metadata between versions."""
        source_meta = self.source.metadata or {}
        target_meta = self.target.metadata or {}

        source_keys = set(source_meta.keys())
        target_keys = set(target_meta.keys())

        # Added metadata
        for key in target_keys - source_keys:
            report.add_change(Change(
                change_type=ChangeType.ADDED,
                element_type=ElementType.METADATA,
                element_name=key,
                path=f"metadata:{key}",
                new_value=str(target_meta[key]),
            ))

        # Removed metadata
        for key in source_keys - target_keys:
            report.add_change(Change(
                change_type=ChangeType.REMOVED,
                element_type=ElementType.METADATA,
                element_name=key,
                path=f"metadata:{key}",
                old_value=str(source_meta[key]),
            ))

        # Modified metadata
        for key in source_keys & target_keys:
            if source_meta[key] != target_meta[key]:
                report.add_change(Change(
                    change_type=ChangeType.MODIFIED,
                    element_type=ElementType.METADATA,
                    element_name=key,
                    path=f"metadata:{key}",
                    old_value=str(source_meta[key]),
                    new_value=str(target_meta[key]),
                ))


class OntologyMerge:
    """
    Merge two ontology versions.

    Supports:
    - Three-way merge (base, ours, theirs)
    - Conflict detection
    - Auto-resolution for non-conflicting changes
    """

    def __init__(self, base: Ontology, ours: Ontology, theirs: Ontology):
        """
        Initialize merge tool.

        Args:
            base: Common ancestor version
            ours: Our modified version
            theirs: Their modified version
        """
        self.base = base
        self.ours = ours
        self.theirs = theirs
        self.conflicts: List[Dict[str, Any]] = []

    def merge(self, strategy: str = "ours") -> Tuple[Ontology, List[Dict[str, Any]]]:
        """
        Perform three-way merge.

        Args:
            strategy: Conflict resolution strategy ("ours", "theirs", "manual")

        Returns:
            Tuple of (merged ontology, list of conflicts)
        """
        # Diff both versions against base
        our_diff = OntologyDiff(self.base, self.ours).diff()
        their_diff = OntologyDiff(self.base, self.theirs).diff()

        # Detect conflicts (same element changed in both)
        our_paths = {c.path for c in our_diff.changes}
        their_paths = {c.path for c in their_diff.changes}
        conflict_paths = our_paths & their_paths

        # Build merged ontology
        merged_entities = self._merge_entities(our_diff, their_diff, conflict_paths, strategy)
        merged_relationships = self._merge_relationships(our_diff, their_diff, conflict_paths, strategy)
        merged_rules = self._merge_rules(our_diff, their_diff, conflict_paths, strategy)

        merged = Ontology(
            name=self.ours.name,
            version=self._increment_version(self.ours.version),
            source=self.ours.source,
            entities=merged_entities,
            relationships=merged_relationships,
            business_rules=merged_rules,
            metadata={
                **self.base.metadata,
                **self.theirs.metadata,
                **self.ours.metadata,
                "merged_from": [self.ours.name, self.theirs.name],
            },
        )

        return merged, self.conflicts

    def _merge_entities(
        self,
        our_diff: DiffReport,
        their_diff: DiffReport,
        conflict_paths: Set[str],
        strategy: str,
    ) -> List[OntologyEntity]:
        """Merge entities from both versions."""
        # Start with our entities
        merged = {e.name: e for e in self.ours.entities}

        # Add their new entities
        for change in their_diff.changes:
            if (
                change.element_type == ElementType.ENTITY
                and change.change_type == ChangeType.ADDED
            ):
                # Check if we also added it
                if change.path not in conflict_paths:
                    # Find the entity in theirs
                    for e in self.theirs.entities:
                        if e.name == change.element_name:
                            merged[e.name] = e
                            break
                else:
                    self._record_conflict(change.path, "entity", strategy)

        return list(merged.values())

    def _merge_relationships(
        self,
        our_diff: DiffReport,
        their_diff: DiffReport,
        conflict_paths: Set[str],
        strategy: str,
    ) -> List[OntologyRelationship]:
        """Merge relationships from both versions."""
        merged = {f"{r.from_entity}→{r.to_entity}": r for r in self.ours.relationships}

        for change in their_diff.changes:
            if (
                change.element_type == ElementType.RELATIONSHIP
                and change.change_type == ChangeType.ADDED
            ):
                if change.path not in conflict_paths:
                    for r in self.theirs.relationships:
                        key = f"{r.from_entity}→{r.to_entity}"
                        if key == change.element_name:
                            merged[key] = r
                            break
                else:
                    self._record_conflict(change.path, "relationship", strategy)

        return list(merged.values())

    def _merge_rules(
        self,
        our_diff: DiffReport,
        their_diff: DiffReport,
        conflict_paths: Set[str],
        strategy: str,
    ) -> List[BusinessRule]:
        """Merge business rules from both versions."""
        merged = {r.name: r for r in self.ours.business_rules}

        for change in their_diff.changes:
            if (
                change.element_type == ElementType.RULE
                and change.change_type == ChangeType.ADDED
            ):
                if change.path not in conflict_paths:
                    for r in self.theirs.business_rules:
                        if r.name == change.element_name:
                            merged[r.name] = r
                            break
                else:
                    self._record_conflict(change.path, "rule", strategy)

        return list(merged.values())

    def _record_conflict(self, path: str, element_type: str, strategy: str):
        """Record a merge conflict."""
        self.conflicts.append({
            "path": path,
            "element_type": element_type,
            "resolution": strategy,
        })

    def _increment_version(self, version: str) -> str:
        """Increment version number."""
        parts = version.split(".")
        if len(parts) >= 2:
            try:
                parts[-1] = str(int(parts[-1]) + 1)
                return ".".join(parts)
            except ValueError:
                pass
        return f"{version}.1"


def diff_ontologies(source: Ontology, target: Ontology) -> DiffReport:
    """
    Convenience function to diff two ontologies.

    Args:
        source: Original ontology
        target: Updated ontology

    Returns:
        DiffReport with all changes
    """
    differ = OntologyDiff(source, target)
    return differ.diff()


def merge_ontologies(
    base: Ontology,
    ours: Ontology,
    theirs: Ontology,
    strategy: str = "ours",
) -> Tuple[Ontology, List[Dict[str, Any]]]:
    """
    Convenience function to merge ontologies.

    Args:
        base: Common ancestor
        ours: Our version
        theirs: Their version
        strategy: Conflict resolution strategy

    Returns:
        Tuple of (merged ontology, conflicts)
    """
    merger = OntologyMerge(base, ours, theirs)
    return merger.merge(strategy)
