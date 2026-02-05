"""
Pydantic models for MCP Server.

Defines request/response models for all MCP tools.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class ExportFormat(str, Enum):
    """OWL export formats."""
    XML = "xml"
    TURTLE = "turtle"
    JSON_LD = "json-ld"
    N3 = "n3"


class MergeStrategy(str, Enum):
    """Ontology merge strategies."""
    OURS = "ours"
    THEIRS = "theirs"
    UNION = "union"


@dataclass
class ExtractResult:
    """Result of pbix_extract tool."""
    success: bool
    entities_count: int = 0
    relationships_count: int = 0
    measures_count: int = 0
    security_rules_count: int = 0
    model_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    source_file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GenerateResult:
    """Result of ontology_generate tool."""
    success: bool
    ontology_data: Dict[str, Any] = field(default_factory=dict)
    patterns_detected: List[str] = field(default_factory=list)
    enhancements_suggested: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExportOWLResult:
    """Result of export_owl tool."""
    success: bool
    owl_content: str = ""
    summary: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExportJSONResult:
    """Result of export_json tool."""
    success: bool
    json_content: str = ""
    output_path: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DebtConflict:
    """Single semantic conflict."""
    conflict_type: str
    severity: str
    name: str
    sources: List[str]
    description: str
    recommendation: str


@dataclass
class AnalyzeDebtResult:
    """Result of analyze_debt tool."""
    success: bool
    total_conflicts: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    report_markdown: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiffChange:
    """Single change in diff."""
    change_type: str
    element_type: str
    path: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    details: str = ""


@dataclass
class DiffResult:
    """Result of ontology_diff tool."""
    success: bool
    has_changes: bool = False
    total_changes: int = 0
    added: int = 0
    removed: int = 0
    modified: int = 0
    changes: List[Dict[str, Any]] = field(default_factory=list)
    changelog: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MergeConflict:
    """Single merge conflict."""
    path: str
    element_type: str
    resolution: str


@dataclass
class MergeResult:
    """Result of ontology_merge tool."""
    success: bool
    merged_ontology: Dict[str, Any] = field(default_factory=dict)
    conflicts_count: int = 0
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    new_version: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChatResult:
    """Result of ontology_chat_ask tool."""
    success: bool
    answer: str = ""
    suggested_questions: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
