"""
MCP Server for PowerBI Ontology Extractor.

This module provides an MCP server that exposes PowerBI ontology extraction
and analysis capabilities as MCP tools, allowing AI agents to work with
Power BI semantic models through the Model Context Protocol.

Usage:
    python -m powerbi_ontology.mcp_server

    Or configure in MCP client with:
    {
        "mcpServers": {
            "powerbi-ontology": {
                "command": "python",
                "args": ["-m", "powerbi_ontology.mcp_server"],
                "cwd": "/path/to/powerbi-ontology-extractor",
                "env": {
                    "POWERBI_MCP_CONFIG": "config/mcp_config.yaml",
                    "OPENAI_API_KEY": "${OPENAI_API_KEY}"
                }
            }
        }
    }
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastmcp import FastMCP
except ImportError:
    raise ImportError(
        "fastmcp is required for MCP server. Install with: pip install fastmcp"
    )

from powerbi_ontology.mcp_config import get_config, reload_config
from powerbi_ontology.mcp_models import (
    ExtractResult,
    GenerateResult,
    ExportOWLResult,
    ExportJSONResult,
    AnalyzeDebtResult,
    DiffResult,
    MergeResult,
    ChatResult,
    ExportFormat,
    MergeStrategy,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize configuration
config = get_config()

# Set log level from config
logging.getLogger().setLevel(getattr(logging, config.log_level, logging.INFO))

# Initialize FastMCP server
mcp = FastMCP("PowerBI-Ontology")


# ============================================================================
# Helper functions
# ============================================================================

def _semantic_model_to_dict(model) -> Dict[str, Any]:
    """Convert SemanticModel to dictionary."""
    return {
        "name": model.name,
        "source_file": model.source_file,
        "entities": [
            {
                "name": e.name,
                "description": e.description,
                "source_table": e.source_table,
                "primary_key": e.primary_key,
                "properties": [
                    {
                        "name": p.name,
                        "data_type": p.data_type,
                        "required": p.required,
                        "unique": p.unique,
                        "description": p.description,
                        "source_column": p.source_column,
                    }
                    for p in e.properties
                ],
            }
            for e in model.entities
        ],
        "relationships": [
            {
                "from_entity": r.from_entity,
                "from_property": r.from_property,
                "to_entity": r.to_entity,
                "to_property": r.to_property,
                "cardinality": r.cardinality,
                "cross_filter_direction": r.cross_filter_direction,
                "is_active": r.is_active,
                "name": r.name,
            }
            for r in model.relationships
        ],
        "measures": [
            {
                "name": m.name,
                "dax_formula": m.dax_formula,
                "description": m.description,
                "folder": m.folder,
                "table": m.table,
                "dependencies": m.dependencies,
            }
            for m in model.measures
        ],
        "hierarchies": [
            {
                "name": h.name,
                "table": h.table,
                "levels": h.levels,
                "hierarchy_type": h.hierarchy_type,
            }
            for h in model.hierarchies
        ],
        "security_rules": [
            {
                "role": s.role,
                "table": s.table,
                "dax_filter": s.dax_filter,
                "description": s.description,
            }
            for s in model.security_rules
        ],
        "metadata": model.metadata,
    }


def _ontology_to_dict(ontology) -> Dict[str, Any]:
    """Convert Ontology to dictionary."""
    return {
        "name": ontology.name,
        "version": ontology.version,
        "source": ontology.source,
        "entities": [
            {
                "name": e.name,
                "description": e.description,
                "entity_type": e.entity_type,
                "source_table": e.source_table,
                "properties": [
                    {
                        "name": p.name,
                        "data_type": p.data_type,
                        "required": p.required,
                        "unique": p.unique,
                        "description": p.description,
                        "source_column": p.source_column,
                        "constraints": [
                            {"type": c.type, "value": c.value, "message": c.message}
                            for c in (p.constraints or [])
                        ],
                    }
                    for p in e.properties
                ],
                "constraints": [
                    {"type": c.type, "value": c.value, "message": c.message}
                    for c in (e.constraints or [])
                ],
            }
            for e in ontology.entities
        ],
        "relationships": [
            {
                "from_entity": r.from_entity,
                "from_property": r.from_property,
                "to_entity": r.to_entity,
                "to_property": r.to_property,
                "relationship_type": r.relationship_type,
                "cardinality": r.cardinality,
                "description": r.description,
                "source_relationship": r.source_relationship,
            }
            for r in ontology.relationships
        ],
        "business_rules": [
            {
                "name": r.name,
                "entity": r.entity,
                "condition": r.condition,
                "action": r.action,
                "classification": r.classification,
                "description": r.description,
                "priority": r.priority,
                "source_measure": r.source_measure,
            }
            for r in ontology.business_rules
        ],
        "metadata": ontology.metadata or {},
    }


def _dict_to_ontology(data: Dict[str, Any]):
    """Convert dictionary to Ontology object."""
    from powerbi_ontology.ontology_generator import (
        Ontology,
        OntologyEntity,
        OntologyProperty,
        OntologyRelationship,
        BusinessRule,
        Constraint,
    )

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
                source_column=p_data.get("source_column", ""),
                constraints=constraints,
            ))

        entity_constraints = [
            Constraint(type=c["type"], value=c["value"], message=c.get("message", ""))
            for c in e_data.get("constraints", [])
        ]

        entities.append(OntologyEntity(
            name=e_data["name"],
            description=e_data.get("description", ""),
            entity_type=e_data.get("entity_type", "standard"),
            source_table=e_data.get("source_table", ""),
            properties=props,
            constraints=entity_constraints,
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
            source_relationship=r_data.get("source_relationship", ""),
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
            source_measure=b_data.get("source_measure", ""),
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


# ============================================================================
# MCP Tool Implementations
# ============================================================================

def _pbix_extract_impl(
    pbix_path: str,
    include_measures: bool = True,
    include_security: bool = True,
) -> Dict[str, Any]:
    """
    Extract semantic model from a Power BI .pbix file.

    This tool extracts the complete semantic model including:
    - Tables/Entities with columns and data types
    - Relationships between tables
    - DAX measures and calculated columns
    - Row-Level Security (RLS) rules
    - Hierarchies

    Args:
        pbix_path: Path to the .pbix file
        include_measures: Whether to extract DAX measures (default: true)
        include_security: Whether to extract RLS rules (default: true)

    Returns:
        Dictionary containing:
        - success (bool): Whether extraction succeeded
        - entities_count (int): Number of entities extracted
        - relationships_count (int): Number of relationships
        - measures_count (int): Number of DAX measures
        - security_rules_count (int): Number of RLS rules
        - model_data (dict): Complete semantic model data

    Example:
        {
            "pbix_path": "/path/to/Sales.pbix",
            "include_measures": true,
            "include_security": true
        }
    """
    logger.info(f"Extracting semantic model from: {pbix_path}")

    try:
        from powerbi_ontology.extractor import PowerBIExtractor

        # Validate file exists
        path = Path(pbix_path)
        if not path.exists():
            return ExtractResult(
                success=False,
                error=f"File not found: {pbix_path}"
            ).to_dict()

        if not path.suffix.lower() == ".pbix":
            return ExtractResult(
                success=False,
                error=f"Invalid file type: {path.suffix}. Expected .pbix"
            ).to_dict()

        # Check file size
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > config.max_file_size_mb:
            return ExtractResult(
                success=False,
                error=f"File too large: {file_size_mb:.1f}MB. Max: {config.max_file_size_mb}MB"
            ).to_dict()

        # Extract
        extractor = PowerBIExtractor(str(path))
        semantic_model = extractor.extract()

        # Convert to dict
        model_data = _semantic_model_to_dict(semantic_model)

        # Optionally exclude measures or security
        if not include_measures:
            model_data["measures"] = []

        if not include_security:
            model_data["security_rules"] = []

        result = ExtractResult(
            success=True,
            entities_count=len(semantic_model.entities),
            relationships_count=len(semantic_model.relationships),
            measures_count=len(semantic_model.measures) if include_measures else 0,
            security_rules_count=len(semantic_model.security_rules) if include_security else 0,
            model_data=model_data,
            source_file=str(path.absolute()),
        )

        logger.info(
            f"Extracted: {result.entities_count} entities, "
            f"{result.relationships_count} relationships, "
            f"{result.measures_count} measures"
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        return ExtractResult(
            success=False,
            error=f"Extraction failed: {str(e)}"
        ).to_dict()


def _ontology_generate_impl(
    model_data: Dict[str, Any],
    detect_patterns: bool = True,
) -> Dict[str, Any]:
    """
    Generate an ontology from a semantic model.

    This tool converts a Power BI semantic model (from pbix_extract) into
    a formal ontology with entities, relationships, and business rules.

    The generator:
    - Maps tables to ontology entities
    - Converts relationships to semantic relationships
    - Extracts business rules from DAX measures
    - Detects patterns (date tables, dimensions, facts)
    - Suggests enhancements

    Args:
        model_data: Semantic model data from pbix_extract
        detect_patterns: Whether to detect common patterns (default: true)

    Returns:
        Dictionary containing:
        - success (bool): Whether generation succeeded
        - ontology_data (dict): Generated ontology
        - patterns_detected (list): List of detected patterns
        - enhancements_suggested (int): Number of suggested enhancements

    Example:
        {
            "model_data": {...},  // Output from pbix_extract
            "detect_patterns": true
        }
    """
    logger.info("Generating ontology from semantic model")

    try:
        from powerbi_ontology.extractor import (
            SemanticModel,
            Entity,
            Property,
            Relationship,
            Measure,
            Hierarchy,
            SecurityRule,
        )
        from powerbi_ontology.ontology_generator import OntologyGenerator

        # Reconstruct SemanticModel from dict
        entities = []
        for e_data in model_data.get("entities", []):
            props = [
                Property(
                    name=p["name"],
                    data_type=p.get("data_type", "String"),
                    required=p.get("required", False),
                    unique=p.get("unique", False),
                    description=p.get("description", ""),
                    source_column=p.get("source_column", ""),
                )
                for p in e_data.get("properties", [])
            ]
            entities.append(Entity(
                name=e_data["name"],
                description=e_data.get("description", ""),
                properties=props,
                source_table=e_data.get("source_table", ""),
                primary_key=e_data.get("primary_key"),
            ))

        relationships = [
            Relationship(
                from_entity=r["from_entity"],
                from_property=r.get("from_property", ""),
                to_entity=r["to_entity"],
                to_property=r.get("to_property", ""),
                cardinality=r.get("cardinality", "many-to-one"),
                cross_filter_direction=r.get("cross_filter_direction", "single"),
                is_active=r.get("is_active", True),
                name=r.get("name", ""),
            )
            for r in model_data.get("relationships", [])
        ]

        measures = [
            Measure(
                name=m["name"],
                dax_formula=m.get("dax_formula", ""),
                description=m.get("description", ""),
                folder=m.get("folder", ""),
                table=m.get("table", ""),
                dependencies=m.get("dependencies", []),
            )
            for m in model_data.get("measures", [])
        ]

        hierarchies = [
            Hierarchy(
                name=h["name"],
                table=h.get("table", ""),
                levels=h.get("levels", []),
                hierarchy_type=h.get("hierarchy_type", "custom"),
            )
            for h in model_data.get("hierarchies", [])
        ]

        security_rules = [
            SecurityRule(
                role=s["role"],
                table=s.get("table", ""),
                dax_filter=s.get("dax_filter", ""),
                description=s.get("description", ""),
            )
            for s in model_data.get("security_rules", [])
        ]

        semantic_model = SemanticModel(
            name=model_data.get("name", "Unnamed"),
            entities=entities,
            relationships=relationships,
            measures=measures,
            hierarchies=hierarchies,
            security_rules=security_rules,
            metadata=model_data.get("metadata", {}),
            source_file=model_data.get("source_file", ""),
        )

        # Generate ontology
        generator = OntologyGenerator(semantic_model)
        ontology = generator.generate()

        # Detect patterns
        patterns_detected = []
        if detect_patterns:
            patterns = generator.detect_patterns()
            patterns_detected = [
                f"{p.pattern_type}: {p.entity_name} ({p.confidence:.0%})"
                for p in patterns
            ]

        # Suggest enhancements
        enhancements = generator.suggest_enhancements()

        result = GenerateResult(
            success=True,
            ontology_data=_ontology_to_dict(ontology),
            patterns_detected=patterns_detected,
            enhancements_suggested=len(enhancements),
        )

        logger.info(
            f"Generated ontology with {len(ontology.entities)} entities, "
            f"{len(ontology.relationships)} relationships, "
            f"{len(ontology.business_rules)} rules"
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        return GenerateResult(
            success=False,
            error=f"Generation failed: {str(e)}"
        ).to_dict()


def _export_owl_impl(
    ontology_data: Dict[str, Any],
    format: str = "xml",
    include_action_rules: bool = True,
) -> Dict[str, Any]:
    """
    Export ontology to OWL format.

    This tool exports an ontology to OWL/RDF format for use with:
    - Triple stores (Blazegraph, Virtuoso)
    - OntoGuard semantic validation
    - Other semantic web tools

    The export includes:
    - OWL classes for entities
    - Datatype properties for columns
    - Object properties for relationships
    - Action rules for OntoGuard (if enabled)
    - Constraints as OWL restrictions

    Args:
        ontology_data: Ontology data from ontology_generate
        format: Output format - "xml", "turtle", "json-ld", "n3" (default: xml)
        include_action_rules: Generate OntoGuard-compatible action rules (default: true)

    Returns:
        Dictionary containing:
        - success (bool): Whether export succeeded
        - owl_content (str): OWL content in requested format
        - summary (dict): Export statistics

    Example:
        {
            "ontology_data": {...},  // Output from ontology_generate
            "format": "turtle",
            "include_action_rules": true
        }
    """
    logger.info(f"Exporting ontology to OWL format: {format}")

    try:
        from powerbi_ontology.export.owl import OWLExporter

        # Convert dict to Ontology
        ontology = _dict_to_ontology(ontology_data)

        # Create exporter
        exporter = OWLExporter(
            ontology,
            include_action_rules=include_action_rules,
            include_constraints=config.include_constraints,
            default_roles=config.default_roles,
        )

        # Export
        owl_content = exporter.export(format=format)
        summary = exporter.get_export_summary()

        result = ExportOWLResult(
            success=True,
            owl_content=owl_content,
            summary=summary,
        )

        logger.info(
            f"Exported OWL with {summary.get('total_triples', 0)} triples, "
            f"{summary.get('classes', 0)} classes"
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return ExportOWLResult(
            success=False,
            error=f"Export failed: {str(e)}"
        ).to_dict()


def _export_json_impl(
    ontology_data: Dict[str, Any],
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Export ontology to JSON format.

    This tool exports an ontology to JSON format for:
    - Storage and versioning
    - Loading in Streamlit UI
    - Integration with other tools

    Args:
        ontology_data: Ontology data from ontology_generate
        output_path: Optional file path to save (if None, returns content only)

    Returns:
        Dictionary containing:
        - success (bool): Whether export succeeded
        - json_content (str): JSON content
        - output_path (str): Path where file was saved (if requested)

    Example:
        {
            "ontology_data": {...},
            "output_path": "/path/to/output.json"
        }
    """
    logger.info("Exporting ontology to JSON format")

    try:
        json_content = json.dumps(ontology_data, indent=2, ensure_ascii=False)

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_content, encoding="utf-8")
            logger.info(f"Saved JSON to: {output_path}")

        result = ExportJSONResult(
            success=True,
            json_content=json_content,
            output_path=output_path,
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return ExportJSONResult(
            success=False,
            error=f"Export failed: {str(e)}"
        ).to_dict()


def _analyze_debt_impl(
    ontologies: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Analyze semantic debt across multiple ontologies.

    This tool detects conflicting definitions between Power BI dashboards:
    - Measures with same name but different DAX formulas
    - Properties with same name but different data types
    - Entities with same name but different structures
    - Conflicting business rules

    Use case: Detect when "Revenue" is defined differently in Sales.pbix vs Finance.pbix

    Args:
        ontologies: Dictionary mapping names to ontology data
                   (must have at least 2 ontologies)

    Returns:
        Dictionary containing:
        - success (bool): Whether analysis succeeded
        - total_conflicts (int): Total number of conflicts
        - critical_count (int): Number of critical conflicts
        - warning_count (int): Number of warnings
        - info_count (int): Number of info-level issues
        - conflicts (list): List of conflict details
        - report_markdown (str): Markdown report

    Example:
        {
            "ontologies": {
                "Sales.pbix": {...},
                "Finance.pbix": {...}
            }
        }
    """
    logger.info(f"Analyzing semantic debt across {len(ontologies)} ontologies")

    try:
        from powerbi_ontology.semantic_debt import SemanticDebtAnalyzer

        if len(ontologies) < 2:
            return AnalyzeDebtResult(
                success=False,
                error="Need at least 2 ontologies for comparison"
            ).to_dict()

        analyzer = SemanticDebtAnalyzer(
            similarity_threshold=config.similarity_threshold
        )

        # Add ontologies
        for name, ont_data in ontologies.items():
            ontology = _dict_to_ontology(ont_data)
            analyzer.add_ontology(name, ontology)

        # Analyze
        report = analyzer.analyze()

        result = AnalyzeDebtResult(
            success=True,
            total_conflicts=len(report.conflicts),
            critical_count=report.summary.get("critical", 0),
            warning_count=report.summary.get("warning", 0),
            info_count=report.summary.get("info", 0),
            conflicts=[c.to_dict() for c in report.conflicts],
            report_markdown=report.to_markdown(),
        )

        logger.info(
            f"Analysis complete: {result.total_conflicts} conflicts "
            f"({result.critical_count} critical)"
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return AnalyzeDebtResult(
            success=False,
            error=f"Analysis failed: {str(e)}"
        ).to_dict()


def _ontology_diff_impl(
    source_ontology: Dict[str, Any],
    target_ontology: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compare two ontology versions.

    This tool provides Git-like diff functionality for ontologies:
    - Detect added elements
    - Detect removed elements
    - Detect modified elements
    - Generate changelog

    Use case: Track changes between ontology versions

    Args:
        source_ontology: Original/old ontology version
        target_ontology: New/updated ontology version

    Returns:
        Dictionary containing:
        - success (bool): Whether diff succeeded
        - has_changes (bool): Whether any changes were detected
        - total_changes (int): Total number of changes
        - added (int): Number of added elements
        - removed (int): Number of removed elements
        - modified (int): Number of modified elements
        - changes (list): List of change details
        - changelog (str): Markdown changelog

    Example:
        {
            "source_ontology": {...},  // v1
            "target_ontology": {...}   // v2
        }
    """
    logger.info("Comparing ontology versions")

    try:
        from powerbi_ontology.ontology_diff import OntologyDiff

        source = _dict_to_ontology(source_ontology)
        target = _dict_to_ontology(target_ontology)

        differ = OntologyDiff(source, target)
        report = differ.diff()

        result = DiffResult(
            success=True,
            has_changes=report.has_changes(),
            total_changes=len(report.changes),
            added=report.summary.get("added", 0),
            removed=report.summary.get("removed", 0),
            modified=report.summary.get("modified", 0),
            changes=[c.to_dict() for c in report.changes],
            changelog=report.to_changelog(),
        )

        logger.info(
            f"Diff complete: {result.total_changes} changes "
            f"(+{result.added} -{result.removed} ~{result.modified})"
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Diff failed: {e}", exc_info=True)
        return DiffResult(
            success=False,
            error=f"Diff failed: {str(e)}"
        ).to_dict()


def _ontology_merge_impl(
    base_ontology: Dict[str, Any],
    ours_ontology: Dict[str, Any],
    theirs_ontology: Dict[str, Any],
    strategy: str = "ours",
) -> Dict[str, Any]:
    """
    Merge two ontology versions with a common base.

    This tool performs three-way merge of ontologies:
    - Combines changes from both versions
    - Detects conflicts
    - Applies resolution strategy

    Strategies:
    - "ours": Prefer our changes on conflicts
    - "theirs": Prefer their changes on conflicts
    - "union": Include both (may cause duplicates)

    Args:
        base_ontology: Common ancestor version
        ours_ontology: Our modified version
        theirs_ontology: Their modified version
        strategy: Conflict resolution - "ours", "theirs", "union" (default: ours)

    Returns:
        Dictionary containing:
        - success (bool): Whether merge succeeded
        - merged_ontology (dict): Merged ontology data
        - conflicts_count (int): Number of conflicts encountered
        - conflicts (list): List of conflict details
        - new_version (str): Version number of merged ontology

    Example:
        {
            "base_ontology": {...},   // common ancestor
            "ours_ontology": {...},   // our changes
            "theirs_ontology": {...}, // their changes
            "strategy": "ours"
        }
    """
    logger.info(f"Merging ontologies with strategy: {strategy}")

    try:
        from powerbi_ontology.ontology_diff import OntologyMerge

        base = _dict_to_ontology(base_ontology)
        ours = _dict_to_ontology(ours_ontology)
        theirs = _dict_to_ontology(theirs_ontology)

        merger = OntologyMerge(base, ours, theirs)
        merged, conflicts = merger.merge(strategy=strategy)

        result = MergeResult(
            success=True,
            merged_ontology=_ontology_to_dict(merged),
            conflicts_count=len(conflicts),
            conflicts=conflicts,
            new_version=merged.version,
        )

        logger.info(
            f"Merge complete: version {result.new_version}, "
            f"{result.conflicts_count} conflicts"
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Merge failed: {e}", exc_info=True)
        return MergeResult(
            success=False,
            error=f"Merge failed: {str(e)}"
        ).to_dict()


def _ontology_chat_ask_impl(
    question: str,
    ontology_data: Dict[str, Any],
    user_role: str = "Analyst",
) -> Dict[str, Any]:
    """
    Ask a question about an ontology using AI.

    This tool uses OpenAI API to answer questions about ontology content:
    - Entity structure and relationships
    - DAX measures and calculations
    - Business rules and permissions
    - Data model analysis

    Requires OPENAI_API_KEY environment variable.

    Args:
        question: Question in natural language (Russian or English)
        ontology_data: Ontology data to query
        user_role: User's role for permission context (default: Analyst)

    Returns:
        Dictionary containing:
        - success (bool): Whether query succeeded
        - answer (str): AI-generated answer
        - suggested_questions (list): Follow-up question suggestions

    Example:
        {
            "question": "Какие entities связаны с Customer?",
            "ontology_data": {...},
            "user_role": "Analyst"
        }
    """
    logger.info(f"Processing chat question: {question[:50]}...")

    try:
        from powerbi_ontology.chat import OntologyChat

        # Check for API key
        if not os.getenv("OPENAI_API_KEY"):
            return ChatResult(
                success=False,
                error="OPENAI_API_KEY not set. Chat requires OpenAI API access."
            ).to_dict()

        # Convert to Ontology
        ontology = _dict_to_ontology(ontology_data)

        # Create chat instance
        chat = OntologyChat(
            model=config.chat_model,
        )

        # Ask question
        answer = chat.ask(
            question=question,
            ontology=ontology,
            user_role=user_role,
            include_history=False,  # Stateless for MCP
        )

        # Get suggestions
        suggestions = chat.get_suggestions(ontology)

        result = ChatResult(
            success=True,
            answer=answer,
            suggested_questions=suggestions,
        )

        logger.info("Chat response generated successfully")

        return result.to_dict()

    except Exception as e:
        logger.error(f"Chat failed: {e}", exc_info=True)
        return ChatResult(
            success=False,
            error=f"Chat failed: {str(e)}"
        ).to_dict()


# ============================================================================
# MCP Tool Registration
# ============================================================================

@mcp.tool()
def pbix_extract(
    pbix_path: str,
    include_measures: bool = True,
    include_security: bool = True,
) -> Dict[str, Any]:
    """Extract semantic model from a Power BI .pbix file."""
    return _pbix_extract_impl(pbix_path, include_measures, include_security)


@mcp.tool()
def ontology_generate(
    model_data: Dict[str, Any],
    detect_patterns: bool = True,
) -> Dict[str, Any]:
    """Generate an ontology from a semantic model."""
    return _ontology_generate_impl(model_data, detect_patterns)


@mcp.tool()
def export_owl(
    ontology_data: Dict[str, Any],
    format: str = "xml",
    include_action_rules: bool = True,
) -> Dict[str, Any]:
    """Export ontology to OWL format."""
    return _export_owl_impl(ontology_data, format, include_action_rules)


@mcp.tool()
def export_json(
    ontology_data: Dict[str, Any],
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Export ontology to JSON format."""
    return _export_json_impl(ontology_data, output_path)


@mcp.tool()
def analyze_debt(
    ontologies: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Analyze semantic debt across multiple ontologies."""
    return _analyze_debt_impl(ontologies)


@mcp.tool()
def ontology_diff(
    source_ontology: Dict[str, Any],
    target_ontology: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare two ontology versions."""
    return _ontology_diff_impl(source_ontology, target_ontology)


@mcp.tool()
def ontology_merge(
    base_ontology: Dict[str, Any],
    ours_ontology: Dict[str, Any],
    theirs_ontology: Dict[str, Any],
    strategy: str = "ours",
) -> Dict[str, Any]:
    """Merge two ontology versions with a common base."""
    return _ontology_merge_impl(base_ontology, ours_ontology, theirs_ontology, strategy)


@mcp.tool()
def ontology_chat_ask(
    question: str,
    ontology_data: Dict[str, Any],
    user_role: str = "Analyst",
) -> Dict[str, Any]:
    """Ask a question about an ontology using AI."""
    return _ontology_chat_ask_impl(question, ontology_data, user_role)


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Main entry point for the MCP server."""
    logger.info(f"Starting {config.server_name} v{config.server_version}")
    logger.info(f"Log level: {config.log_level}")
    mcp.run()


if __name__ == "__main__":
    main()
