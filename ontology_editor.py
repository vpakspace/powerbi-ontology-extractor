"""
Visual Ontology Editor - No-Code UI for Power BI Ontology Management.

A Streamlit-based GUI for:
- Loading ontologies from .pbix files or JSON
- Editing entities, properties, and relationships
- Adding permissions (read/write/execute) per role
- Adding business rules and constraints
- Previewing generated OWL
- Real-time validation

Run: streamlit run ontology_editor.py
"""

import hashlib
import json
import logging
import tempfile
import secrets
import os
import zipfile
from pathlib import Path
from datetime import datetime

import streamlit as st

# Audit logger for tracking user operations
audit_logger = logging.getLogger("ontology_editor.audit")
if not audit_logger.handlers:
    _log_dir = Path(__file__).parent / "data"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _handler = logging.FileHandler(str(_log_dir / "audit.log"), encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    audit_logger.addHandler(_handler)
    audit_logger.setLevel(logging.INFO)

# Security constants
MAX_PBIX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_CHAT_HISTORY = 50  # Maximum chat messages to retain in session

# Default roles (single source of truth for the editor)
DEFAULT_ROLES = ["Admin", "Analyst", "Viewer"]

# Storage directory for auto-saved ontologies
STORAGE_DIR = Path(__file__).parent / "data" / "ontologies"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def validate_pbix_upload(uploaded_file) -> str | None:
    """
    Validate uploaded .pbix file for security.

    Returns None if valid, or an error message string.
    """
    # Check file size
    uploaded_file.seek(0, os.SEEK_END)
    size = uploaded_file.tell()
    uploaded_file.seek(0)

    if size > MAX_PBIX_FILE_SIZE:
        return f"File too large: {size / (1024*1024):.1f} MB (max {MAX_PBIX_FILE_SIZE // (1024*1024)} MB)"

    if size == 0:
        return "File is empty"

    # Validate ZIP structure (.pbix is a ZIP archive)
    try:
        with zipfile.ZipFile(uploaded_file) as zf:
            for name in zf.namelist():
                # Reject path traversal attempts
                if name.startswith('/') or '..' in name:
                    return f"Rejected: suspicious path in archive: {name}"
                # Reject absolute Windows paths
                if len(name) > 1 and name[1] == ':':
                    return f"Rejected: absolute path in archive: {name}"
    except zipfile.BadZipFile:
        return "Invalid .pbix file: not a valid ZIP archive"
    finally:
        uploaded_file.seek(0)

    return None

from powerbi_ontology.ontology_generator import (
    Ontology,
    OntologyEntity,
    OntologyProperty,
    OntologyRelationship,
    BusinessRule,
    Constraint,
)
from powerbi_ontology.export.owl import OWLExporter
from powerbi_ontology.contract_builder import ContractBuilder
from powerbi_ontology.ontology_diff import OntologyDiff, OntologyMerge
from powerbi_ontology.semantic_debt import SemanticDebtAnalyzer
from powerbi_ontology.chat import create_chat

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Page config
st.set_page_config(
    page_title="Ontology Editor",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    """Initialize session state variables."""
    if "ontology" not in st.session_state:
        st.session_state.ontology = None
    if "selected_entity" not in st.session_state:
        st.session_state.selected_entity = None
    if "permissions" not in st.session_state:
        st.session_state.permissions = {}
    if "roles" not in st.session_state:
        st.session_state.roles = list(DEFAULT_ROLES)
    if "loaded_file" not in st.session_state:
        st.session_state.loaded_file = None  # Track loaded file to prevent re-processing
    if "compare_ontology" not in st.session_state:
        st.session_state.compare_ontology = None  # Second ontology for diff/merge
    if "diff_report" not in st.session_state:
        st.session_state.diff_report = None
    if "merged_ontology" not in st.session_state:
        st.session_state.merged_ontology = None
    # Chat state
    if "chat_instance" not in st.session_state:
        st.session_state.chat_instance = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "chat_role" not in st.session_state:
        st.session_state.chat_role = "Analyst"


def get_safe_filename(name: str) -> str:
    """Convert ontology name to safe filename."""
    # Replace unsafe characters
    safe = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    safe = "".join(c for c in safe if c.isalnum() or c in "_-.")
    return safe[:100]  # Limit length


def autosave_ontology(ontology: Ontology) -> Path:
    """Auto-save ontology to storage directory. Returns path to saved file."""
    safe_name = get_safe_filename(ontology.name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_name}_{timestamp}.json"
    filepath = STORAGE_DIR / filename

    # Convert ontology to JSON-serializable dict
    data = ontology_to_dict(ontology)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return filepath


def get_recent_ontologies(limit: int = 10) -> list:
    """Get list of recently saved ontologies, sorted by modification time."""
    files = []
    for f in STORAGE_DIR.glob("*.json"):
        try:
            stat = f.stat()
            files.append({
                "path": f,
                "name": f.stem,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "size": stat.st_size,
            })
        except OSError:
            continue

    # Sort by modification time, newest first
    files.sort(key=lambda x: x["modified"], reverse=True)
    return files[:limit]


def load_from_storage(filepath: Path) -> Ontology:
    """Load ontology from storage file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return load_ontology_from_json(data)


def create_empty_ontology(name: str) -> Ontology:
    """Create a new empty ontology."""
    return Ontology(
        name=name,
        version="1.0.0",
        source="Manual",
        entities=[],
        relationships=[],
        business_rules=[],
        metadata={"created_by": "Ontology Editor"},
    )


def load_ontology_from_json(json_data: dict) -> Ontology:
    """Load ontology from JSON data."""
    entities = []
    for entity_data in json_data.get("entities", []):
        properties = []
        for prop_data in entity_data.get("properties", []):
            constraints = []
            for c in prop_data.get("constraints", []):
                constraints.append(Constraint(
                    type=c.get("type", ""),
                    value=c.get("value"),
                    message=c.get("message", ""),
                ))
            properties.append(OntologyProperty(
                name=prop_data.get("name", ""),
                data_type=prop_data.get("data_type", "String"),
                required=prop_data.get("required", False),
                unique=prop_data.get("unique", False),
                constraints=constraints,
                description=prop_data.get("description", ""),
            ))

        entity_constraints = []
        for c in entity_data.get("constraints", []):
            entity_constraints.append(Constraint(
                type=c.get("type", ""),
                value=c.get("value"),
                message=c.get("message", ""),
            ))

        entities.append(OntologyEntity(
            name=entity_data.get("name", ""),
            description=entity_data.get("description", ""),
            properties=properties,
            constraints=entity_constraints,
            entity_type=entity_data.get("entity_type", "standard"),
        ))

    relationships = []
    for rel_data in json_data.get("relationships", []):
        relationships.append(OntologyRelationship(
            from_entity=rel_data.get("from_entity", ""),
            to_entity=rel_data.get("to_entity", ""),
            from_property=rel_data.get("from_property", ""),
            to_property=rel_data.get("to_property", ""),
            relationship_type=rel_data.get("relationship_type", "related_to"),
            cardinality=rel_data.get("cardinality", "one-to-many"),
            description=rel_data.get("description", ""),
        ))

    business_rules = []
    for rule_data in json_data.get("business_rules", []):
        business_rules.append(BusinessRule(
            name=rule_data.get("name", ""),
            entity=rule_data.get("entity", ""),
            condition=rule_data.get("condition", ""),
            action=rule_data.get("action", ""),
            classification=rule_data.get("classification", ""),
            description=rule_data.get("description", ""),
            priority=rule_data.get("priority", 1),
        ))

    return Ontology(
        name=json_data.get("name", "Unnamed"),
        version=json_data.get("version", "1.0.0"),
        source=json_data.get("source", "JSON Import"),
        entities=entities,
        relationships=relationships,
        business_rules=business_rules,
        metadata=json_data.get("metadata", {}),
    )


def ontology_to_dict(ontology: Ontology) -> dict:
    """Convert ontology to JSON-serializable dict."""
    return {
        "name": ontology.name,
        "version": ontology.version,
        "source": ontology.source,
        "entities": [
            {
                "name": e.name,
                "description": e.description,
                "entity_type": e.entity_type,
                "properties": [
                    {
                        "name": p.name,
                        "data_type": p.data_type,
                        "required": p.required,
                        "unique": p.unique,
                        "description": p.description,
                        "constraints": [
                            {"type": c.type, "value": c.value, "message": c.message}
                            for c in p.constraints
                        ],
                    }
                    for p in e.properties
                ],
                "constraints": [
                    {"type": c.type, "value": c.value, "message": c.message}
                    for c in e.constraints
                ],
            }
            for e in ontology.entities
        ],
        "relationships": [
            {
                "from_entity": r.from_entity,
                "to_entity": r.to_entity,
                "from_property": r.from_property,
                "to_property": r.to_property,
                "relationship_type": r.relationship_type,
                "cardinality": r.cardinality,
                "description": r.description,
            }
            for r in ontology.relationships
        ],
        "business_rules": [
            {
                "name": b.name,
                "entity": b.entity,
                "condition": b.condition,
                "action": b.action,
                "classification": b.classification,
                "description": b.description,
                "priority": b.priority,
            }
            for b in ontology.business_rules
        ],
        "metadata": ontology.metadata,
    }


def render_sidebar():
    """Render sidebar with ontology info and actions."""
    st.sidebar.title("🔧 Ontology Editor")

    if st.session_state.ontology:
        ont = st.session_state.ontology
        st.sidebar.success(f"**{ont.name}** v{ont.version}")
        st.sidebar.caption(f"Source: {ont.source}")

        st.sidebar.divider()

        # Stats
        st.sidebar.metric("Entities", len(ont.entities))
        st.sidebar.metric("Relationships", len(ont.relationships))
        st.sidebar.metric("Business Rules", len(ont.business_rules))

        st.sidebar.divider()

        # Export buttons
        if st.sidebar.button("📥 Export JSON", use_container_width=True):
            json_str = json.dumps(ontology_to_dict(ont), indent=2)
            st.sidebar.download_button(
                "Download JSON",
                json_str,
                f"{ont.name}.json",
                "application/json",
                use_container_width=True,
            )

        if st.sidebar.button("📥 Export OWL", use_container_width=True):
            exporter = OWLExporter(ont, default_roles=st.session_state.roles)
            owl_content = exporter.export(format="xml")
            audit_logger.info(f"OWL exported: {ont.name} ({len(owl_content)} bytes)")
            st.sidebar.download_button(
                "Download OWL",
                owl_content,
                f"{ont.name}.owl",
                "application/xml",
                use_container_width=True,
            )

        st.sidebar.divider()

        # Autosave button
        if st.sidebar.button("💾 Save to History", use_container_width=True):
            filepath = autosave_ontology(ont)
            audit_logger.info(f"Ontology saved: {ont.name} → {filepath.name}")
            st.sidebar.success(f"Saved: {filepath.name}")

        if st.sidebar.button("🗑️ Clear Ontology", use_container_width=True, type="secondary"):
            st.session_state.ontology = None
            st.session_state.selected_entity = None
            st.session_state.loaded_file = None  # Reset to allow re-loading
            st.rerun()
    else:
        st.sidebar.info("No ontology loaded. Create or import one.")

    # Recent ontologies section
    st.sidebar.divider()
    st.sidebar.subheader("📚 Recent Ontologies")

    recent = get_recent_ontologies(limit=5)
    if recent:
        for item in recent:
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                # Truncate long names
                display_name = item["name"][:25] + "..." if len(item["name"]) > 25 else item["name"]
                st.caption(f"📄 {display_name}")
                st.caption(f"   {item['modified'].strftime('%m/%d %H:%M')}")
            with col2:
                if st.button("📂", key=f"load_{item['path'].name}", help=f"Load {item['name']}"):
                    try:
                        st.session_state.ontology = load_from_storage(item["path"])
                        st.session_state.loaded_file = None  # Reset tracking
                        st.rerun()
                    except Exception as e:
                        st.sidebar.error(f"Error: {e}")
    else:
        st.sidebar.caption("No saved ontologies yet")


def render_load_tab():
    """Render Load/Create ontology tab."""
    st.header("📂 Load or Create Ontology")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Create New")
        new_name = st.text_input("Ontology Name", value="My_Ontology")
        if st.button("Create Empty Ontology", type="primary"):
            st.session_state.ontology = create_empty_ontology(new_name)
            st.success(f"Created ontology: {new_name}")
            st.rerun()

    with col2:
        st.subheader("Import")

        # JSON import
        uploaded_json = st.file_uploader("Upload JSON", type=["json"])
        if uploaded_json:
            try:
                json_data = json.load(uploaded_json)
                st.session_state.ontology = load_ontology_from_json(json_data)
                st.success(f"Loaded: {st.session_state.ontology.name}")
                st.rerun()
            except Exception as e:
                st.error(f"Error loading JSON: {e}")

        st.divider()

        # PBIX import (if available)
        uploaded_pbix = st.file_uploader("Upload .pbix", type=["pbix"])
        if uploaded_pbix:
            # Prevent re-processing the same file on rerun
            file_key = f"{uploaded_pbix.name}_{uploaded_pbix.size}"
            if st.session_state.loaded_file == file_key:
                st.info(f"✅ Already loaded: {uploaded_pbix.name}")
            else:
                # Validate uploaded file before processing
                validation_error = validate_pbix_upload(uploaded_pbix)
                if validation_error:
                    st.error(f"Upload rejected: {validation_error}")
                else:
                    temp_path = None
                    try:
                        # Save to temp file with unpredictable name and restrictive permissions
                        temp_dir = Path(tempfile.gettempdir())
                        temp_name = f"pbix_{secrets.token_hex(16)}.pbix"
                        temp_path = str(temp_dir / temp_name)
                        fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                        with os.fdopen(fd, 'wb') as f:
                            f.write(uploaded_pbix.read())

                        # Try to extract
                        from powerbi_ontology.extractor import PowerBIExtractor
                        from powerbi_ontology.ontology_generator import OntologyGenerator

                        with st.spinner(f"Extracting {uploaded_pbix.name}..."):
                            extractor = PowerBIExtractor(temp_path)
                            semantic_model = extractor.extract()
                            generator = OntologyGenerator(semantic_model)
                            st.session_state.ontology = generator.generate()

                        # Mark file as loaded to prevent re-processing
                        st.session_state.loaded_file = file_key
                        audit_logger.info(f"PBIX uploaded: {uploaded_pbix.name} ({uploaded_pbix.size} bytes)")
                        st.success(f"✅ Extracted ontology from {uploaded_pbix.name}")
                        st.rerun()
                    except Exception as e:
                        audit_logger.warning(f"PBIX upload failed: {uploaded_pbix.name} — {e}")
                        st.error(f"Error extracting from PBIX: {e}")
                    finally:
                        if temp_path:
                            Path(temp_path).unlink(missing_ok=True)


def render_entities_tab():
    """Render Entities editing tab."""
    st.header("📦 Entities")

    if not st.session_state.ontology:
        st.warning("Load or create an ontology first.")
        return

    ont = st.session_state.ontology

    # Entity list
    col1, col2 = st.columns([1, 3])

    with col1:
        st.subheader("Entity List")

        # Add new entity
        with st.expander("➕ Add Entity"):
            new_entity_name = st.text_input("Entity Name", key="new_entity_name")
            new_entity_desc = st.text_area("Description", key="new_entity_desc", height=68)
            new_entity_type = st.selectbox(
                "Type",
                ["standard", "dimension", "fact", "bridge", "date"],
                key="new_entity_type",
            )
            if st.button("Add Entity"):
                if new_entity_name and new_entity_name not in [e.name for e in ont.entities]:
                    ont.entities.append(OntologyEntity(
                        name=new_entity_name,
                        description=new_entity_desc,
                        entity_type=new_entity_type,
                        properties=[],
                        constraints=[],
                    ))
                    st.session_state.selected_entity = new_entity_name
                    audit_logger.info(f"Entity added: {new_entity_name} (type={new_entity_type})")
                    st.success(f"Added entity: {new_entity_name}")
                    st.rerun()
                else:
                    st.error("Entity name required and must be unique.")

        # List entities
        for entity in ont.entities:
            btn_type = "primary" if st.session_state.selected_entity == entity.name else "secondary"
            if st.button(
                f"📦 {entity.name}",
                key=f"entity_{entity.name}",
                use_container_width=True,
                type=btn_type,
            ):
                st.session_state.selected_entity = entity.name
                st.rerun()

    with col2:
        if st.session_state.selected_entity:
            entity = next(
                (e for e in ont.entities if e.name == st.session_state.selected_entity),
                None,
            )
            if entity:
                render_entity_editor(entity)


def render_entity_editor(entity: OntologyEntity):
    """Render entity editor."""
    st.subheader(f"Edit: {entity.name}")

    # Basic info
    with st.expander("Basic Info", expanded=True):
        entity.description = st.text_area(
            "Description",
            value=entity.description,
            key=f"desc_{entity.name}",
        )
        entity.entity_type = st.selectbox(
            "Entity Type",
            ["standard", "dimension", "fact", "bridge", "date"],
            index=["standard", "dimension", "fact", "bridge", "date"].index(entity.entity_type or "standard"),
            key=f"type_{entity.name}",
        )

    # Properties
    st.subheader("Properties")

    # Add property
    with st.expander("➕ Add Property"):
        prop_col1, prop_col2 = st.columns(2)
        with prop_col1:
            new_prop_name = st.text_input("Property Name", key="new_prop_name")
            new_prop_type = st.selectbox(
                "Data Type",
                ["String", "Integer", "Decimal", "Boolean", "DateTime", "Date"],
                key="new_prop_type",
            )
        with prop_col2:
            new_prop_required = st.checkbox("Required", key="new_prop_required")
            new_prop_unique = st.checkbox("Unique", key="new_prop_unique")
        new_prop_desc = st.text_input("Description", key="new_prop_desc")

        if st.button("Add Property"):
            if new_prop_name and new_prop_name not in [p.name for p in entity.properties]:
                entity.properties.append(OntologyProperty(
                    name=new_prop_name,
                    data_type=new_prop_type,
                    required=new_prop_required,
                    unique=new_prop_unique,
                    description=new_prop_desc,
                    constraints=[],
                ))
                st.success(f"Added property: {new_prop_name}")
                st.rerun()
            else:
                st.error("Property name required and must be unique.")

    # List properties
    if entity.properties:
        for prop in entity.properties:
            with st.expander(f"📌 {prop.name} ({prop.data_type})", expanded=False):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    prop.description = st.text_input(
                        "Description",
                        value=prop.description,
                        key=f"prop_desc_{entity.name}_{prop.name}",
                    )
                with col2:
                    prop.required = st.checkbox(
                        "Required",
                        value=prop.required,
                        key=f"prop_req_{entity.name}_{prop.name}",
                    )
                with col3:
                    prop.unique = st.checkbox(
                        "Unique",
                        value=prop.unique,
                        key=f"prop_uniq_{entity.name}_{prop.name}",
                    )

                # Constraints
                st.caption("Constraints")
                constraint_type = st.selectbox(
                    "Add Constraint",
                    ["", "range", "regex", "enum"],
                    key=f"constraint_type_{entity.name}_{prop.name}",
                )
                if constraint_type == "range":
                    c1, c2 = st.columns(2)
                    min_val = c1.number_input("Min", key=f"min_{entity.name}_{prop.name}")
                    max_val = c2.number_input("Max", key=f"max_{entity.name}_{prop.name}")
                    if st.button("Add Range", key=f"add_range_{entity.name}_{prop.name}"):
                        prop.constraints.append(Constraint(
                            type="range",
                            value={"min": min_val, "max": max_val},
                            message=f"Value must be between {min_val} and {max_val}",
                        ))
                        st.rerun()
                elif constraint_type == "regex":
                    pattern = st.text_input("Pattern", key=f"pattern_{entity.name}_{prop.name}")
                    if st.button("Add Pattern", key=f"add_pattern_{entity.name}_{prop.name}"):
                        prop.constraints.append(Constraint(
                            type="regex",
                            value=pattern,
                            message=f"Must match pattern: {pattern}",
                        ))
                        st.rerun()
                elif constraint_type == "enum":
                    enum_values = st.text_input(
                        "Values (comma-separated)",
                        key=f"enum_{entity.name}_{prop.name}",
                    )
                    if st.button("Add Enum", key=f"add_enum_{entity.name}_{prop.name}"):
                        prop.constraints.append(Constraint(
                            type="enum",
                            value=[v.strip() for v in enum_values.split(",")],
                            message=f"Must be one of: {enum_values}",
                        ))
                        st.rerun()

                # Show existing constraints
                if prop.constraints:
                    for c in prop.constraints:
                        st.caption(f"• {c.type}: {c.value}")

                # Delete button
                if st.button("🗑️ Delete Property", key=f"del_prop_{entity.name}_{prop.name}"):
                    entity.properties.remove(prop)
                    st.rerun()
    else:
        st.info("No properties. Add one above.")

    # Delete entity
    st.divider()
    if st.button("🗑️ Delete Entity", type="secondary"):
        ont = st.session_state.ontology
        audit_logger.info(f"Entity deleted: {entity.name}")
        ont.entities = [e for e in ont.entities if e.name != entity.name]
        ont.relationships = [
            r for r in ont.relationships
            if r.from_entity != entity.name and r.to_entity != entity.name
        ]
        st.session_state.selected_entity = None
        st.rerun()


def render_relationships_tab():
    """Render Relationships editing tab."""
    st.header("🔗 Relationships")

    if not st.session_state.ontology:
        st.warning("Load or create an ontology first.")
        return

    ont = st.session_state.ontology
    entity_names = [e.name for e in ont.entities]

    if not entity_names:
        st.warning("Add entities first before creating relationships.")
        return

    # Add relationship
    with st.expander("➕ Add Relationship", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            from_entity = st.selectbox("From Entity", entity_names, key="rel_from")
            from_entity_obj = next((e for e in ont.entities if e.name == from_entity), None)
            from_props = [p.name for p in from_entity_obj.properties] if from_entity_obj else []
            from_prop = st.selectbox("From Property", [""] + from_props, key="rel_from_prop")

        with col2:
            rel_type = st.selectbox(
                "Relationship Type",
                ["has", "belongs_to", "contains", "related_to", "references"],
                key="rel_type",
            )
            cardinality = st.selectbox(
                "Cardinality",
                ["one-to-many", "many-to-one", "many-to-many", "one-to-one"],
                key="rel_cardinality",
            )

        with col3:
            to_entity = st.selectbox("To Entity", entity_names, key="rel_to")
            to_entity_obj = next((e for e in ont.entities if e.name == to_entity), None)
            to_props = [p.name for p in to_entity_obj.properties] if to_entity_obj else []
            to_prop = st.selectbox("To Property", [""] + to_props, key="rel_to_prop")

        rel_desc = st.text_input("Description", key="rel_desc")

        if st.button("Add Relationship", type="primary"):
            if from_entity and to_entity and from_entity != to_entity:
                ont.relationships.append(OntologyRelationship(
                    from_entity=from_entity,
                    to_entity=to_entity,
                    from_property=from_prop,
                    to_property=to_prop,
                    relationship_type=rel_type,
                    cardinality=cardinality,
                    description=rel_desc,
                ))
                st.success(f"Added relationship: {from_entity} → {to_entity}")
                st.rerun()
            else:
                st.error("Select different from/to entities.")

    # List relationships
    st.subheader("Existing Relationships")

    if ont.relationships:
        for i, rel in enumerate(ont.relationships):
            with st.expander(f"🔗 {rel.from_entity} → {rel.to_entity} ({rel.relationship_type})"):
                st.write(f"**Type:** {rel.relationship_type}")
                st.write(f"**Cardinality:** {rel.cardinality}")
                if rel.from_property:
                    st.write(f"**From:** {rel.from_entity}.{rel.from_property}")
                if rel.to_property:
                    st.write(f"**To:** {rel.to_entity}.{rel.to_property}")
                if rel.description:
                    st.write(f"**Description:** {rel.description}")

                if st.button("🗑️ Delete", key=f"del_rel_{i}"):
                    ont.relationships.remove(rel)
                    st.rerun()
    else:
        st.info("No relationships defined.")


def render_permissions_tab():
    """Render Permissions (RBAC) editing tab."""
    st.header("🔐 Permissions")

    if not st.session_state.ontology:
        st.warning("Load or create an ontology first.")
        return

    ont = st.session_state.ontology
    entity_names = [e.name for e in ont.entities]

    if not entity_names:
        st.warning("Add entities first before configuring permissions.")
        return

    # Roles management
    with st.expander("👥 Manage Roles"):
        roles_str = st.text_input(
            "Roles (comma-separated)",
            value=", ".join(st.session_state.roles),
        )
        if st.button("Update Roles"):
            st.session_state.roles = [r.strip() for r in roles_str.split(",") if r.strip()]
            st.success(f"Roles updated: {st.session_state.roles}")

    st.subheader("Permission Matrix")
    st.caption("Configure read/write/execute permissions for each role × entity")

    # Initialize permissions
    for role in st.session_state.roles:
        if role not in st.session_state.permissions:
            st.session_state.permissions[role] = {
                "read": [],
                "write": {},
                "execute": [],
            }

    # Permission matrix
    tabs = st.tabs(st.session_state.roles)

    for tab, role in zip(tabs, st.session_state.roles):
        with tab:
            perms = st.session_state.permissions[role]

            st.subheader(f"📋 {role} Permissions")

            # Read permissions
            st.write("**Read Access**")
            read_entities = st.multiselect(
                "Can read entities",
                entity_names,
                default=[e for e in perms["read"] if e in entity_names],
                key=f"read_{role}",
            )
            perms["read"] = read_entities

            # Write permissions
            st.write("**Write Access**")
            for entity_name in entity_names:
                entity = next((e for e in ont.entities if e.name == entity_name), None)
                if entity:
                    prop_names = [p.name for p in entity.properties]
                    if prop_names:
                        write_props = st.multiselect(
                            f"{entity_name} properties",
                            prop_names,
                            default=perms["write"].get(entity_name, []),
                            key=f"write_{role}_{entity_name}",
                        )
                        if write_props:
                            perms["write"][entity_name] = write_props
                        elif entity_name in perms["write"]:
                            del perms["write"][entity_name]

            # Execute permissions
            st.write("**Execute Actions**")
            actions_input = st.text_input(
                "Custom actions (comma-separated)",
                value=", ".join(perms["execute"]),
                key=f"execute_{role}",
                placeholder="approve_order, send_notification, ...",
            )
            perms["execute"] = [a.strip() for a in actions_input.split(",") if a.strip()]

    # Generate contract preview
    st.divider()
    st.subheader("Contract Preview")

    selected_role = st.selectbox("Preview contract for role", st.session_state.roles)

    if st.button("Generate Contract"):
        try:
            perms = st.session_state.permissions[selected_role]
            builder = ContractBuilder(ont)
            contract = builder.build_contract(
                f"{selected_role}Agent",
                {
                    "read": perms["read"],
                    "write": perms["write"],
                    "execute": perms["execute"],
                    "role": selected_role,
                }
            )

            st.json({
                "agent_name": contract.agent_name,
                "role": contract.permissions.required_role,
                "read_entities": contract.permissions.read_entities,
                "write_properties": contract.permissions.write_properties,
                "executable_actions": contract.permissions.executable_actions,
            })
        except Exception as e:
            st.error(f"Error generating contract: {e}")


def render_business_rules_tab():
    """Render Business Rules editing tab."""
    st.header("📜 Business Rules")

    if not st.session_state.ontology:
        st.warning("Load or create an ontology first.")
        return

    ont = st.session_state.ontology
    entity_names = [e.name for e in ont.entities]

    # Add rule
    with st.expander("➕ Add Business Rule", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            rule_name = st.text_input("Rule Name", key="rule_name")
            rule_entity = st.selectbox("Applies to Entity", [""] + entity_names, key="rule_entity")
            rule_condition = st.text_input("Condition (DAX/expression)", key="rule_condition")
        with col2:
            rule_action = st.text_input("Action", key="rule_action", placeholder="RequireApproval")
            rule_class = st.selectbox(
                "Classification",
                ["low", "medium", "high", "critical"],
                key="rule_class",
            )
            rule_priority = st.number_input("Priority", min_value=1, max_value=10, value=1, key="rule_priority")

        rule_desc = st.text_area("Description", key="rule_desc", height=68)

        if st.button("Add Rule", type="primary"):
            if rule_name:
                ont.business_rules.append(BusinessRule(
                    name=rule_name,
                    entity=rule_entity,
                    condition=rule_condition,
                    action=rule_action,
                    classification=rule_class,
                    description=rule_desc,
                    priority=int(rule_priority),
                ))
                st.success(f"Added rule: {rule_name}")
                st.rerun()
            else:
                st.error("Rule name required.")

    # List rules
    st.subheader("Existing Rules")

    if ont.business_rules:
        for i, rule in enumerate(ont.business_rules):
            severity_colors = {
                "low": "🟢",
                "medium": "🟡",
                "high": "🟠",
                "critical": "🔴",
            }
            icon = severity_colors.get(rule.classification, "⚪")

            with st.expander(f"{icon} {rule.name} ({rule.entity})"):
                st.write(f"**Condition:** `{rule.condition}`")
                st.write(f"**Action:** {rule.action}")
                st.write(f"**Classification:** {rule.classification}")
                st.write(f"**Priority:** {rule.priority}")
                if rule.description:
                    st.write(f"**Description:** {rule.description}")

                if st.button("🗑️ Delete", key=f"del_rule_{i}"):
                    ont.business_rules.remove(rule)
                    st.rerun()
    else:
        st.info("No business rules defined.")


def render_owl_preview_tab():
    """Render OWL Preview tab."""
    st.header("🦉 OWL Preview")

    if not st.session_state.ontology:
        st.warning("Load or create an ontology first.")
        return

    ont = st.session_state.ontology

    # Export options
    col1, col2, col3 = st.columns(3)
    with col1:
        format_choice = st.selectbox("Format", ["xml", "turtle", "n3"])
    with col2:
        include_actions = st.checkbox("Include Action Rules", value=True)
    with col3:
        include_constraints = st.checkbox("Include Constraints", value=True)

    # Generate preview
    if st.button("Generate OWL", type="primary"):
        try:
            exporter = OWLExporter(
                ont,
                default_roles=st.session_state.roles,
                include_action_rules=include_actions,
                include_constraints=include_constraints,
            )
            owl_content = exporter.export(format=format_choice)

            # Summary
            summary = exporter.get_export_summary()

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Triples", summary["total_triples"])
            col2.metric("Classes", summary["classes"])
            col3.metric("Properties", summary["datatype_properties"] + summary["object_properties"])
            col4.metric("Action Rules", summary["action_rules"])

            # Code preview
            st.code(owl_content, language="xml" if format_choice == "xml" else "turtle")

            # Download
            st.download_button(
                "📥 Download OWL",
                owl_content,
                f"{ont.name}.owl",
                "application/xml" if format_choice == "xml" else "text/turtle",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Error generating OWL: {e}")


def render_diff_merge_tab():
    """Render Diff & Merge tab."""
    st.header("🔀 Diff & Merge")

    if not st.session_state.ontology:
        st.warning("Load or create an ontology first (Tab 1).")
        return

    ont = st.session_state.ontology

    st.info(f"**Current ontology**: {ont.name} ({len(ont.entities)} entities)")

    # Upload second ontology for comparison
    st.subheader("📂 Load Second Ontology for Comparison")

    col1, col2 = st.columns(2)

    with col1:
        uploaded_json = st.file_uploader("Upload JSON ontology", type=["json"], key="diff_json")
        if uploaded_json:
            try:
                json_data = json.load(uploaded_json)
                st.session_state.compare_ontology = load_ontology_from_json(json_data)
                st.success(f"Loaded: {st.session_state.compare_ontology.name}")
            except Exception as e:
                st.error(f"Error loading JSON: {e}")

    with col2:
        uploaded_pbix = st.file_uploader("Upload .pbix file", type=["pbix"], key="diff_pbix")
        if uploaded_pbix:
            file_key = f"diff_{uploaded_pbix.name}_{uploaded_pbix.size}"
            if st.session_state.get("diff_loaded_file") != file_key:
                temp_path = None
                try:
                    with tempfile.NamedTemporaryFile(suffix=".pbix", delete=False) as f:
                        f.write(uploaded_pbix.read())
                        temp_path = f.name

                    from powerbi_ontology.extractor import PowerBIExtractor
                    from powerbi_ontology.ontology_generator import OntologyGenerator

                    with st.spinner(f"Extracting {uploaded_pbix.name}..."):
                        extractor = PowerBIExtractor(temp_path)
                        semantic_model = extractor.extract()
                        generator = OntologyGenerator(semantic_model)
                        st.session_state.compare_ontology = generator.generate()

                    st.session_state["diff_loaded_file"] = file_key
                    st.success(f"Extracted: {st.session_state.compare_ontology.name}")
                except Exception as e:
                    st.error(f"Error extracting from PBIX: {e}")
                finally:
                    if temp_path:
                        Path(temp_path).unlink(missing_ok=True)

    # Show comparison info
    if st.session_state.compare_ontology:
        comp = st.session_state.compare_ontology
        st.success(f"**Compare ontology**: {comp.name} ({len(comp.entities)} entities)")

        st.divider()

        # Diff section
        st.subheader("📊 Diff (Compare)")

        if st.button("🔍 Run Diff", type="primary"):
            try:
                differ = OntologyDiff(ont, comp)
                st.session_state.diff_report = differ.diff()
                st.success("Diff completed!")
            except Exception as e:
                st.error(f"Error running diff: {e}")

        if st.session_state.diff_report:
            report = st.session_state.diff_report

            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Changes", report.total_changes)
            col2.metric("➕ Added", report.added_count)
            col3.metric("➖ Removed", report.removed_count)
            col4.metric("📝 Modified", report.modified_count)

            # Changelog
            with st.expander("📋 View Changelog", expanded=True):
                st.markdown(report.to_changelog())

            # Download
            st.download_button(
                "📥 Download Changelog",
                report.to_changelog(),
                "changelog.md",
                "text/markdown",
            )

        st.divider()

        # Merge section
        st.subheader("🔀 Merge")

        merge_strategy = st.selectbox(
            "Merge Strategy",
            ["union", "ours", "theirs"],
            help="union=combine all, ours=prefer current, theirs=prefer compare"
        )

        if st.button("🔀 Run Merge", type="primary"):
            try:
                merger = OntologyMerge(
                    base=ont,
                    ours=ont,
                    theirs=comp
                )
                merged, conflicts = merger.merge(strategy=merge_strategy)
                st.session_state.merged_ontology = merged

                st.success(f"Merge completed! Result: {len(merged.entities)} entities")

                if conflicts:
                    st.warning(f"⚠️ {len(conflicts)} conflicts detected")
                    with st.expander("View Conflicts"):
                        for c in conflicts:
                            st.write(f"• {c.get('type', 'unknown')}: {c.get('element', '')}")
            except Exception as e:
                st.error(f"Error merging: {e}")

        if st.session_state.merged_ontology:
            merged = st.session_state.merged_ontology

            # Merged stats
            st.write(f"**Merged ontology**: {merged.name}")
            col1, col2, col3 = st.columns(3)
            col1.metric("Entities", len(merged.entities))
            col2.metric("Relationships", len(merged.relationships))
            col3.metric("Business Rules", len(merged.business_rules))

            # Use merged as current
            if st.button("✅ Use Merged as Current Ontology"):
                st.session_state.ontology = merged
                st.session_state.merged_ontology = None
                st.session_state.compare_ontology = None
                st.session_state.diff_report = None
                st.success("Merged ontology is now the current ontology!")
                st.rerun()

        st.divider()

        # Semantic Debt Analysis
        st.subheader("📈 Semantic Debt Analysis")

        if st.button("🔍 Analyze Conflicts"):
            try:
                analyzer = SemanticDebtAnalyzer()
                analyzer.add_ontology(ont.name, ont)
                analyzer.add_ontology(comp.name, comp)
                debt_report = analyzer.analyze()

                st.metric("Total Conflicts", debt_report.total_conflicts)

                col1, col2, col3 = st.columns(3)
                col1.metric("🔴 Critical", debt_report.critical_count)
                col2.metric("🟡 Warning", debt_report.warning_count)
                col3.metric("🔵 Info", debt_report.info_count)

                if debt_report.conflicts:
                    with st.expander("View Conflicts", expanded=True):
                        st.markdown(debt_report.to_markdown())
            except Exception as e:
                st.error(f"Error analyzing: {e}")

    else:
        st.info("👆 Upload a second ontology to compare and merge.")


def render_chat_tab():
    """Render Chat tab for AI-powered Q&A about the ontology."""
    st.header("💬 Ontology Chat")

    if not st.session_state.ontology:
        st.warning("⚠️ Load an ontology first to start chatting.")
        return

    ont = st.session_state.ontology

    # Check if OpenAI API key is configured
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-openai-api-key-here":
        st.error("⚠️ OPENAI_API_KEY not configured. Please set it in .env file.")
        st.code("""
# .env file:
OPENAI_API_KEY=sk-your-actual-key-here
        """)
        return

    # Initialize chat instance
    if st.session_state.chat_instance is None:
        try:
            st.session_state.chat_instance = create_chat()
        except Exception as e:
            st.error(f"Error initializing chat: {e}")
            return

    chat = st.session_state.chat_instance

    # Layout
    col1, col2 = st.columns([3, 1])

    with col2:
        st.subheader("⚙️ Settings")

        # Role selection
        st.session_state.chat_role = st.selectbox(
            "Your Role",
            st.session_state.roles,
            index=st.session_state.roles.index(st.session_state.chat_role)
            if st.session_state.chat_role in st.session_state.roles
            else 0,
        )

        # Ontology info
        st.divider()
        st.caption(f"📊 **{ont.name}**")
        st.caption(f"Entities: {len(ont.entities)}")
        st.caption(f"Relationships: {len(ont.relationships)}")
        st.caption(f"Rules: {len(ont.business_rules)}")

        # Suggested questions
        st.divider()
        st.subheader("💡 Suggestions")
        suggestions = chat.get_suggestions(ont)
        for suggestion in suggestions[:4]:
            sug_key = hashlib.md5(suggestion.encode("utf-8")).hexdigest()[:8]
            if st.button(suggestion[:30] + "..." if len(suggestion) > 30 else suggestion, key=f"sug_{sug_key}"):
                st.session_state.pending_question = suggestion

        # Clear history button
        st.divider()
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            chat.clear_history()
            st.rerun()

    with col1:
        # Chat history display
        chat_container = st.container()

        with chat_container:
            if not st.session_state.chat_history:
                st.info(f"👋 Ask me anything about **{ont.name}**!")
                st.caption("Examples: 'What entities exist?', 'How are Customer and Sales related?'")
            else:
                for msg in st.session_state.chat_history:
                    if msg["role"] == "user":
                        st.chat_message("user").write(msg["content"])
                    else:
                        st.chat_message("assistant").write(msg["content"])

        # Input area
        st.divider()

        # Check for pending question from suggestions
        initial_value = ""
        if "pending_question" in st.session_state:
            initial_value = st.session_state.pending_question
            del st.session_state.pending_question

        # Question input
        question = st.text_input(
            "Your question",
            value=initial_value,
            placeholder="Ask about entities, relationships, measures...",
            key="chat_input",
        )

        col_send, col_spacer = st.columns([1, 4])
        with col_send:
            send_clicked = st.button("🚀 Send", type="primary", use_container_width=True)

        if send_clicked and question:
            # Add user message
            st.session_state.chat_history.append({"role": "user", "content": question})

            # Get AI response
            with st.spinner("Thinking..."):
                try:
                    answer = chat.ask(
                        question=question,
                        ontology=ont,
                        user_role=st.session_state.chat_role,
                    )
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.session_state.chat_history.append({"role": "assistant", "content": error_msg})

            # Trim chat history to prevent memory leak
            if len(st.session_state.chat_history) > MAX_CHAT_HISTORY:
                st.session_state.chat_history = st.session_state.chat_history[-MAX_CHAT_HISTORY:]

            st.rerun()


def main():
    """Main application."""
    init_session_state()
    render_sidebar()

    # Main tabs
    tabs = st.tabs([
        "📂 Load/Create",
        "📦 Entities",
        "🔗 Relationships",
        "🔐 Permissions",
        "📜 Business Rules",
        "🦉 OWL Preview",
        "🔀 Diff & Merge",
        "💬 Chat",
    ])

    with tabs[0]:
        render_load_tab()

    with tabs[1]:
        render_entities_tab()

    with tabs[2]:
        render_relationships_tab()

    with tabs[3]:
        render_permissions_tab()

    with tabs[4]:
        render_business_rules_tab()

    with tabs[5]:
        render_owl_preview_tab()

    with tabs[6]:
        render_diff_merge_tab()

    with tabs[7]:
        render_chat_tab()


if __name__ == "__main__":
    main()
