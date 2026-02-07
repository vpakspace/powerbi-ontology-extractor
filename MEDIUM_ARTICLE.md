# How We Extract Hidden Ontologies from 20 Million Power BI Dashboards and Make Them Accessible to AI Agents

> **TL;DR**: We built an open-source tool that automatically extracts semantic models from Power BI .pbix files and transforms them into formal OWL ontologies. This enables AI agents to work safely with enterprise data by understanding business rules, relationships, and access constraints. `pip install powerbi-ontology-extractor` — and in 10 minutes you have an ontology.

---

## The Problem: $4.6M Lost Due to a Renamed Column

In 2024, a major logistics company lost $4.6M overnight. The cause was absurdly simple: a database administrator renamed a column from `Warehouse_Location` to `FacilityID`. The AI agent managing routing didn't know about the rename and started shipping cargo to random addresses.

This case isn't an exception — it's a symptom of a systemic problem. There are **over 20 million** Power BI dashboards worldwide (Microsoft, 2024). Each one contains a semantic model — tables, relationships, measures, security rules. In essence, every Power BI dashboard is an **informal ontology**, locked inside a proprietary .pbix file.

AI agents can't read .pbix files. They don't know that `Revenue` in the sales department and `Revenue` in finance are different metrics with different formulas. They don't understand that an analyst has read-only access, while only an admin can delete records. Without this knowledge, an AI agent is a blind robot with access to a production database.

### The Scale of the Problem

| Metric | Value |
|--------|-------|
| Power BI dashboards worldwide | 20M+ |
| Average cost of manual ontology creation | $50K–$200K |
| Percentage of ontology that can be extracted automatically | ~70% |
| Percentage requiring manual work by a business analyst | ~30% |

Manual ontology creation takes months of expensive specialist work. Yet 70% of the effort is mechanical extraction of what's already described in Power BI: tables become entities, columns become properties, foreign keys become relationships, DAX formulas become business rules.

---

## The Solution: 30 Minutes Instead of 3 Months

We built **PowerBI Ontology Extractor** — an open-source Python tool that automates those 70% and provides a visual editor for the remaining 30%.

Solution architecture:

```
Power BI (.pbix)  →  Ontology Extractor  →  OntoGuard  →  AI Agent
      10 min              10 min             5 min          5 min
```

What happens at each stage:

1. **Extraction** (10 min): The binary .pbix file is unpacked, DataModel is parsed (via PBIXRay), extracting tables, columns, data types, relationships, DAX measures, and RLS rules
2. **Generation** (10 min): Raw data is transformed into a formal ontology — classes, properties, relationships with cardinality, business rules from DAX, constraints
3. **Validation** (5 min): The ontology passes through OntoGuard (a semantic firewall) that enforces role-based access control via OWL rules
4. **Deployment** (5 min): The AI agent receives the ontology as a contract — and now knows what it can and cannot do

### Installation

```bash
pip install powerbi-ontology-extractor
```

That's it. No Docker, no server configuration, no paid APIs (except optional OpenAI for chat). One command — and you have a CLI, Python API, and Streamlit UI.

### Conceptual Foundation

PowerBI Ontology Extractor translates a Power BI semantic model into an explicit ontological artifact — something that can be queried, validated, versioned, and used as a "semantic contract" for AI agents. The starting idea here comes from a series of articles by [Pankaj Kumar](#references): at enterprise scale, BI models are effectively informal ontologies that can be formalized and turned into an infrastructure asset.

The practical value lies in reliability. When meaning is externalized, it becomes possible to perform "semantic checks" rather than just "schema checks" — for example, business logic validation and safer model changes during field and name drift. This aligns well with Kumar's ideas on semantic validation ([OntoGuard](https://github.com/vpakspace/ontoguard-ai)) and production infrastructure for agents at the intersection of MCP and ontologies ([Universal Agent Connector](https://github.com/vpakspace/universal-agent-connector)).

---

## Under the Hood

### Parsing .pbix Files

Power BI stores data in a binary format. We use the [PBIXRay](https://github.com/pankajkumar/pbixray) library to read the DataModel, then extract:

```python
from powerbi_ontology import PowerBIExtractor

extractor = PowerBIExtractor("sales_dashboard.pbix")
model = extractor.extract()

print(f"Tables:        {len(model.entities)}")
print(f"Relationships: {len(model.relationships)}")
print(f"Measures:      {len(model.measures)}")
print(f"RLS Rules:     {len(model.rls_rules)}")
```

For the real Sales_Returns_Sample.pbix file from Microsoft, this gives:

```
Tables:        15
Relationships: 9
Measures:      58
RLS Rules:     0
```

Each table becomes an `Entity` with typed properties, each relationship becomes a `Relationship` with cardinality (one-to-many, many-to-many) and cross-filter direction.

### DAX → Business Rules

The most interesting part is automatic DAX formula parsing. DAX is the Power BI query language where business logic is encoded:

```dax
Total Revenue = SUMX(Sales, Sales[Quantity] * Sales[Unit Price])

Revenue YoY% =
DIVIDE(
    [Total Revenue] - CALCULATE([Total Revenue], SAMEPERIODLASTYEAR('Date'[Date])),
    CALCULATE([Total Revenue], SAMEPERIODLASTYEAR('Date'[Date]))
)
```

Our DAX parser recognizes:
- **Aggregations**: SUM, AVERAGE, COUNT, SUMX — transformed into calculation rules
- **Conditional logic**: IF, SWITCH, CALCULATE with filters — transformed into business rules
- **Time Intelligence**: SAMEPERIODLASTYEAR, DATEADD — marked as temporal metrics
- **Dependencies**: Which tables and columns each measure uses

This is critically important: an AI agent that knows the Revenue formula won't sum the `Price` column directly — it will use the correct metric.

### OWL Ontology Generation

The extracted model is transformed into a formal OWL ontology:

```python
from powerbi_ontology import OntologyGenerator
from powerbi_ontology.export.owl import OWLExporter

# Generate ontology
ontology = OntologyGenerator(model).generate()

# Export to OWL
exporter = OWLExporter(
    ontology,
    default_roles=["Admin", "Analyst", "Viewer"]
)
exporter.save("sales_ontology.owl")

summary = exporter.get_export_summary()
print(f"OWL Classes:        {summary['classes']}")
print(f"Properties:         {summary['datatype_properties']}")
print(f"Action Rules:       {summary['action_rules']}")
```

The OWL file contains:
- **owl:Class** for each entity (Customer, Sales, Product)
- **owl:DatatypeProperty** for each property with XSD types
- **owl:ObjectProperty** for relationships between entities
- **Action Rules** — who (role) can do what (create/read/update/delete) with which entity
- **Business rules** from DAX measures (as OWL annotations)
- **Constraints** (required, unique, range, enum)

For Sales_Returns_Sample, this generates **1,734 RDF triples** — a complete formal description of the dashboard's semantics.

---

## What's New

### 1. Automatic Extraction, Not Manual Creation

Existing tools (Protege, WebVOWL, TopBraid) assume you **manually** create ontologies. That's expensive ($50K+) and slow (months). We extract 70% of the ontology **automatically** from what already exists in Power BI.

### 2. DAX → Business Rules (Not Just Schema)

Tools like `pbi-tools` or `Tabular Editor` can export Power BI schemas. But a schema is not an ontology. We go further: we parse DAX formulas and transform them into semantic business rules. The AI agent gets not just "a Sales table with a Revenue column," but "Revenue is calculated as SUMX(Sales, Quantity * UnitPrice) and is accessible to Admin and Analyst roles for reading."

### 3. A Bridge Between BI and AI

Power BI is a tool for humans. OWL is a standard for machines. Our extractor is a bridge: humans work in familiar Power BI, while AI agents receive a formal ontology with access rules.

### 4. Schema Drift Detection

Remember the $4.6M story? We solve this problem with Schema Drift Detection:

```python
from powerbi_ontology import SchemaMapper

mapper = SchemaMapper()
# Bind ontology to actual DB schema
drift = mapper.check_drift(ontology, actual_schema)

for issue in drift:
    print(f"[{issue.severity}] {issue.entity}: {issue.description}")
    # [CRITICAL] Sales: Column 'Warehouse_Location' not found (renamed to 'FacilityID'?)
```

The system normalizes types (`varchar(255)` → `text`, `int` → `integer`), detects renames through similarity matching (>70% match), and classifies issues by severity: CRITICAL blocks the agent, WARNING logs, INFO informs.

### 5. Semantic Debt Analysis

When an organization has 50+ dashboards, "semantic debt" inevitably emerges — the same metric defined differently across dashboards:

```python
from powerbi_ontology import analyze_ontologies

report = analyze_ontologies([
    "sales_ontology.json",
    "finance_ontology.json",
    "marketing_ontology.json"
])

for conflict in report.conflicts:
    print(f"Conflict: {conflict.entity}.{conflict.property}")
    print(f"  Dashboard A: {conflict.definition_a}")
    print(f"  Dashboard B: {conflict.definition_b}")
    # Conflict: Revenue
    #   Sales dashboard: SUMX(Sales, Quantity * UnitPrice)
    #   Finance dashboard: SUM(Invoices[Amount]) - SUM(Refunds[Amount])
```

This lets you detect conflicts **before** the AI agent starts using contradictory data.

---

## How to Use It

### Option 1: Python API (for developers)

```bash
pip install powerbi-ontology-extractor
```

```python
from powerbi_ontology import PowerBIExtractor, OntologyGenerator
from powerbi_ontology.export.owl import OWLExporter

# 1. Extract model from .pbix
extractor = PowerBIExtractor("my_dashboard.pbix")
model = extractor.extract()

# 2. Generate ontology
ontology = OntologyGenerator(model).generate()

# 3. Export
# To OWL (for OntoGuard / triple stores)
OWLExporter(ontology).save("ontology.owl")

# To JSON (for API / AI agents)
import json
with open("ontology.json", "w") as f:
    json.dump(ontology.to_dict(), f, indent=2)
```

### Option 2: CLI (for DevOps and automation)

```bash
# Extract a single file
pbix2owl extract -i dashboard.pbix -o ontology.owl

# Batch process a directory (8 parallel workers)
pbix2owl batch -i ./dashboards/ -o ./ontologies/ -w 8 --recursive

# Semantic debt analysis
pbix2owl analyze -i ./ontologies/ -o report.md

# Version comparison
pbix2owl diff -s v1.json -t v2.json -o changelog.md
```

### Option 3: Streamlit UI (for business analysts)

```bash
pip install powerbi-ontology-extractor streamlit
streamlit run ontology_editor.py --server.port 8503
```

A visual editor with 8 tabs:

| Tab | Function |
|-----|----------|
| Load/Create | Upload .pbix or create from scratch |
| Entities | Edit entities and properties |
| Relationships | Manage relationships |
| Permissions | RBAC matrix (role x entity x action) |
| Business Rules | Business rules with classification |
| OWL Preview | Preview and export OWL |
| Diff & Merge | Compare and merge versions |
| AI Chat | Ask questions about the ontology in natural language |

An analyst can upload a .pbix file, edit the automatically extracted ontology (those 30%), ask an AI question ("Which entities are related to Customer?"), and export the result — all without writing a single line of code.

### Option 4: MCP Server (for Claude Code)

PowerBI Ontology Extractor works as an MCP server that you can connect to Claude Code:

```json
// ~/.claude.json
{
  "mcpServers": {
    "powerbi-ontology": {
      "command": "python",
      "args": ["-m", "powerbi_ontology.mcp_server"]
    }
  }
}
```

After this, 8 tools become available in Claude Code: `pbix_extract`, `ontology_generate`, `export_owl`, `export_json`, `analyze_debt`, `ontology_diff`, `ontology_merge`, `ontology_chat_ask`.

You can simply tell Claude: *"Extract the ontology from sales.pbix and export it to OWL"* — and it will do it.

---

## Ecosystem Integration

PowerBI Ontology Extractor is the first element in a chain for safe AI agent interaction with data:

```
┌──────────────────────┐     ┌──────────────────────┐     ┌────────────────────────────┐
│  Ontology Extractor  │────▶│      OntoGuard       │────▶│ Universal Agent Connector  │
│  (this project)      │     │  Semantic Firewall   │     │    MCP Infrastructure     │
│  Extraction          │     │  Validation          │     │    Agent Connection        │
└──────────────────────┘     └──────────────────────┘     └────────────────────────────┘
```

- **[OntoGuard](https://github.com/vpakspace/ontoguard-ai)** — a semantic firewall. It takes the OWL ontology extracted by our tool and checks every AI agent action: "Can the Analyst role delete a record in the Patients table?" If the OWL rule prohibits it — the action is blocked before it reaches the database.

- **[Universal Agent Connector](https://github.com/vpakspace/universal-agent-connector)** — MCP infrastructure for connecting AI agents to databases. Uses OntoGuard as middleware: NL query → SQL → OntoGuard check → execution.

Together they implement a **semantic contract**: the AI agent gets not just data access, but access with understanding of what the data means, how it's connected, and what can be done with it.

---

## Evaluation

We evaluate extraction accuracy on **real Microsoft .pbix samples**, comparing extracted data against manually verified ground truth.

### Entity Extraction Accuracy

| Dataset | Precision | Recall | F1 | Entities |
|---------|-----------|--------|----|----------|
| Sales_Returns_Sample | 87% | 87% | 87% | 15 |
| Adventure_Works_DW_2020 | 100% | 100% | 100% | 11 |

### Relationship Extraction

| Dataset | Precision | Recall | F1 | Relationships |
|---------|-----------|--------|----|---------------|
| Sales_Returns_Sample | 100% | 100% | 100% | 9 |
| Adventure_Works_DW_2020 | 100% | 100% | 100% | 13 |

### DAX Parser Pattern Coverage

**8/8 patterns** handled correctly (100%). The regex-based parser handles: `CALCULATE`, `IF`, `SWITCH`, and simple thresholds. Patterns without conditions (plain SUM, SUMX iterators) are correctly ignored.

### OWL Export

| Dataset | OWL Triples | Business Rules | Extraction Time |
|---------|-------------|----------------|-----------------|
| Sales_Returns_Sample | 1,656 | 32 | 117 ms |
| Adventure_Works_DW_2020 | 1,083 | 0 | 73 ms |

**Limitations**: The regex-based DAX parser does not support nested CALCULATE (inner level), row context iterators (SUMX/FILTER), table constructors, or advanced DAX patterns like SELECTEDVALUE/HASONEVALUE. The evaluation script and ground truth data are available in `evaluation/run_evaluation.py`.

---

## Testing and Security

### 370 Tests, 81% Coverage

```bash
$ pytest
========================= 370 passed in 4.56s =========================
```

We test on real .pbix files from Microsoft (Sales_Returns_Sample, Adventure_Works_DW_2020), not synthetic data.

### Security Hardening (v0.1.1)

In version 0.1.1, 14 security issues discovered during code review were fixed:

| Severity | Count | Examples |
|----------|-------|---------|
| CRITICAL | 3 | Path traversal in file writing, XSS in chat, unsafe YAML |
| HIGH | 2 | API key validation, upload size limit (50 MB) |
| MEDIUM | 4 | Audit logging, DAX parser hardening, chat history limit |
| LOW | 5 | Type hints, deterministic hashing, rate limiting |

All mutating operations (file uploads, exports, edits) are logged in `data/audit.log`.

---

## Authorship and Roadmap

The framework has been significantly rearchitected from the original concept by Kumar, but I deliberately kept entity names and semantic blocks "as the author had them" — so that readers can more easily cross-reference with the original sources without losing the thread of context.

The project is actively evolving. Near-term steps:

- **Richer constraint extraction** — in the spirit of SHACL validations, to express not just types but business invariants (ranges, field dependencies)
- **Change impact analysis** — diffs between model versions with assessment of which agents and pipelines are affected
- **Ontology packaging standardization** — for agent runtime systems (MCP-compatible format, artifact versioning)
- **v0.2.0**: Power BI Semantic Link support (direct connection to Fabric)
- **v0.3.0**: Automatic Semantic Contract generation with property-level permissions
- **v1.0.0**: Production-ready with CI/CD, Docker image, Helm chart

---

## Try It Now

```bash
# Install
pip install powerbi-ontology-extractor

# CLI
pbix2owl extract -i your_dashboard.pbix -o ontology.owl

# Or the visual editor
pip install streamlit
streamlit run ontology_editor.py
```

- **PyPI**: [powerbi-ontology-extractor](https://pypi.org/project/powerbi-ontology-extractor/)
- **GitHub**: [vpakspace/powerbi-ontology-extractor](https://github.com/vpakspace/powerbi-ontology-extractor)
- **Release**: [v0.1.1](https://github.com/vpakspace/powerbi-ontology-extractor/releases/tag/v0.1.1)
- **License**: MIT

---

*If this project is useful — give it a star on GitHub. If you have questions or ideas — open an Issue, we respond.*

---

## References

### Pankaj Kumar's Article Series (conceptual foundation)

1. [Microsoft vs Palantir: Two Paths to Enterprise Ontology](https://medium.com/@cloudpankaj/microsoft-vs-palantir-two-paths-to-enterprise-ontology-and-why-microsofts-bet-on-semantic-6e72265dce21)
2. [The Power BI Ontology Paradox](https://medium.com/@cloudpankaj/the-power-bi-ontology-paradox-how-20-million-dashboards-became-microsofts-secret-weapon-for-5585e7d18c01)
3. [From Power BI Dashboard to AI Agent in 30 Minutes](https://medium.com/@cloudpankaj/from-power-bi-dashboard-to-ai-agent-in-30-minutes-i-built-the-tool-that-unlocks-20-million-hidden-500e59bd91df)
4. [Universal Agent Connector: MCP + Ontology](https://medium.com/@cloudpankaj/universal-agent-connector-mcp-ontology-production-ready-ai-infrastructure-0b4e35f22942)
5. [OntoGuard: Ontology Firewall for AI Agents](https://medium.com/@cloudpankaj/ontoguard-i-built-an-ontology-firewall-for-ai-agents-in-48-hours-using-cursor-ai-be4208c405e7)

### Projects

- [PowerBI Ontology Extractor](https://github.com/vpakspace/powerbi-ontology-extractor) — this project
- [OntoGuard AI](https://github.com/vpakspace/ontoguard-ai) — semantic firewall for AI agents
- [Universal Agent Connector](https://github.com/vpakspace/universal-agent-connector) — MCP infrastructure for connecting agents to databases
