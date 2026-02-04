# PowerBI Ontology Extractor

<div align="center">

![PowerBI Ontology Extractor](https://img.shields.io/badge/PowerBI-Ontology%20Extractor-blue?style=for-the-badge)

**Transform 20 million Power BI dashboards into AI-ready ontologies**

[![Tests](https://img.shields.io/badge/tests-340%20passed-brightgreen)](https://github.com/vpakspace/powerbi-ontology-extractor)
[![Coverage](https://img.shields.io/badge/coverage-82%25-green)](https://github.com/vpakspace/powerbi-ontology-extractor)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[Installation](#installation) • [Quick Start](#-quick-start) • [Features](#-key-features) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## 🎯 The Problem

Enterprises have **20+ million Power BI semantic models** that are actually **informal ontologies** trapped in proprietary .pbix files.

- **The Challenge**: Each Power BI model contains entities, relationships, and business logic—but AI agents can't access this semantic intelligence
- **The Cost**: Enterprises spend $50K-$200K per semantic definition to reconcile conflicts across dashboards
- **The $4.6M Mistake**: A logistics company lost $4.6M when an AI agent used a renamed column (`Warehouse_Location` → `FacilityID`) because there was no semantic binding validation

## 💡 The Solution

PowerBI Ontology Extractor **unlocks the hidden ontologies** in your Power BI dashboards and transforms them into formal, AI-ready ontologies.

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────────────┐
│   Power BI .pbix    │────▶│  Ontology Extractor  │────▶│       OntoGuard             │
│  (20M+ dashboards)  │     │  (this project)      │     │  Semantic Firewall          │
└─────────────────────┘     └──────────────────────┘     └─────────────────────────────┘
                                     │                              │
                                     │ OWL/Fabric IQ                │ Semantic Validation
                                     ▼                              ▼
                            ┌──────────────────────┐     ┌─────────────────────────────┐
                            │   Semantic Contract  │────▶│  Universal Agent Connector  │
                            │   (permissions)      │     │  AI Agent Infrastructure    │
                            └──────────────────────┘     └─────────────────────────────┘
                                                                    │
                                                                    ▼
                                                         ┌─────────────────────────────┐
                                                         │       AI Agents             │
                                                         │  (Claude, GPT, etc.)        │
                                                         └─────────────────────────────┘
```

**30-minute workflow**:
```
Power BI (.pbix) → Ontology Extractor → OntoGuard → Universal Agent Connector → AI Agent
     10 min           10 min            5 min            3 min               2 min
```

---

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/vpakspace/powerbi-ontology-extractor.git
cd powerbi-ontology-extractor

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

### Basic Usage

```python
from powerbi_ontology import PowerBIExtractor, OntologyGenerator

# Step 1: Extract semantic model from Power BI
extractor = PowerBIExtractor("path/to/dashboard.pbix")
semantic_model = extractor.extract()

# Step 2: Generate formal ontology
generator = OntologyGenerator(semantic_model)
ontology = generator.generate()

print(f"✅ Extracted {len(ontology.entities)} entities")
print(f"✅ Found {len(ontology.relationships)} relationships")
print(f"✅ Generated {len(ontology.business_rules)} business rules")

# Step 3: Export to OWL for OntoGuard
from powerbi_ontology.export import OWLExporter

exporter = OWLExporter(ontology)
exporter.save("ontology.owl")
```

### Visual Ontology Editor (No-Code UI)

```bash
# Start Streamlit UI
streamlit run ontology_editor.py --server.port 8503
```

**Features**:
- 📂 Load from .pbix files or JSON
- 📦 Edit entities with properties and constraints
- 🔗 Manage relationships between entities
- 🔐 Configure permission matrix (RBAC)
- 📜 Add business rules with classification
- 🦉 Preview and export OWL
- 🔀 Diff & Merge ontology versions
- 💬 **AI Chat** - Ask questions about your ontology!

---

## 🔥 Key Features

### 1. Automatic Extraction (PBIXRay)
- ✅ Reads Power BI .pbix files (binary DataModel via PBIXRay)
- ✅ Extracts tables, columns, relationships, hierarchies
- ✅ Parses DAX measures and calculated columns
- ✅ Captures Row-Level Security (RLS) rules
- ✅ Fallback to JSON model.bim for legacy files

### 2. DAX to Business Rules
- ✅ Parses DAX formulas automatically
- ✅ Extracts conditional logic (IF, SWITCH, CALCULATE)
- ✅ Converts filters to business rules
- ✅ Classifies measure types (aggregation, conditional, time intelligence)

### 3. Ontology Generation (70% Automated)
- ✅ Entities from tables
- ✅ Properties from columns (with data types)
- ✅ Relationships from foreign keys (with cardinality)
- ✅ Business rules from DAX measures
- ✅ Constraints (required, unique, range, regex, enum)
- ✅ Pattern detection (date tables, dimensions, facts)

### 4. Multi-Format Export
| Format | Use Case |
|--------|----------|
| **OWL/RDF** | OntoGuard semantic validation |
| **Fabric IQ** | Microsoft Fabric deployment |
| **JSON** | Universal agent connector |
| **Semantic Contract** | Role-based AI agent permissions |

### 5. Schema Drift Detection (Prevents $4.6M Mistakes!)
- ✅ Validates schema bindings
- ✅ Detects column renames/deletions
- ✅ Type normalization (varchar→text, int→integer)
- ✅ Severity levels: CRITICAL, WARNING, INFO
- ✅ Auto-fix suggestions

### 6. Multi-Dashboard Semantic Debt Analysis
- ✅ Analyzes multiple Power BI dashboards
- ✅ Detects conflicting definitions ("Revenue" defined differently)
- ✅ 5 conflict types: MEASURE, TYPE, ENTITY, RELATIONSHIP, RULE
- ✅ Generates consolidation reports

### 7. Ontology Diff & Merge
- ✅ Git-like diff between ontology versions
- ✅ Detect added/removed/modified elements
- ✅ Three-way merge (base, ours, theirs)
- ✅ Conflict detection and resolution strategies

### 8. Collaborative Review Workflow
- ✅ Comments on entities/properties/rules
- ✅ Reply and resolve threads
- ✅ Approval workflow: draft → review → approved → published
- ✅ Audit trail of all actions

### 9. CLI Tool for Automation
```bash
# Extract single .pbix file
pbix2owl extract -i dashboard.pbix -o ontology.owl

# Batch process directory (8 parallel workers)
pbix2owl batch -i ./dashboards/ -o ./ontologies/ -w 8 --recursive

# Analyze semantic debt
pbix2owl analyze -i ./ontologies/ -o report.md

# Compare versions (diff)
pbix2owl diff -s v1.json -t v2.json -o changelog.md
```

### 10. AI-Powered Ontology Chat 🆕
- ✅ Ask questions about loaded ontology in natural language
- ✅ OpenAI API integration (gpt-4o-mini)
- ✅ Role-based context (Admin/Analyst/Viewer)
- ✅ Bilingual support (Russian/English)
- ✅ Suggested questions based on ontology content

**Example questions**:
- "What entities exist in the ontology?"
- "How are Customer and Sales related?"
- "Show all DAX measures"
- "What permissions does Analyst role have?"

---

## 📊 Real-World Example

**Tested with Microsoft official samples**:

| File | Size | Entities | Relationships | DAX Measures | OWL Triples |
|------|------|----------|---------------|--------------|-------------|
| Sales_Returns_Sample.pbix | 6.3 MB | 15 | 9 | 58 | 1,734 |
| Adventure_Works_DW_2020.pbix | 7.8 MB | 11 | 13 | 0 | 1,083 |

```python
from powerbi_ontology import PowerBIExtractor, OntologyGenerator
from powerbi_ontology.export import OWLExporter

# Extract from Power BI
extractor = PowerBIExtractor("Sales_Returns_Sample.pbix")
model = extractor.extract()

# Generate ontology
ontology = OntologyGenerator(model).generate()

# Export to OWL (for OntoGuard)
exporter = OWLExporter(ontology, default_roles=["Admin", "Analyst", "Viewer"])
exporter.save("sales_ontology.owl")

# Summary
summary = exporter.get_export_summary()
print(f"Classes: {summary['classes']}")
print(f"Properties: {summary['datatype_properties']}")
print(f"Action Rules: {summary['action_rules']}")  # CRUD per entity × role
```

---

## 🔗 Integration Ecosystem

### OntoGuard (Semantic Firewall)

```python
from powerbi_ontology.export import OWLExporter

exporter = OWLExporter(ontology)
exporter.save("ontology.owl")

# Use with OntoGuard for AI agent validation
# github.com/vpakspace/ontoguard-ai
```

### Universal Agent Connector (MCP)

```python
from powerbi_ontology import ContractBuilder
from powerbi_ontology.export import ContractToOWLConverter

# Create semantic contract for AI agent
builder = ContractBuilder(ontology)
contract = builder.build_contract(
    agent_name="SalesAnalyst",
    permissions={
        "read": ["Customer", "Sales", "Product"],
        "write": {"Sales": ["Status"]},
        "execute": ["GenerateReport"]
    }
)

# Export for MCP
converter = ContractToOWLConverter(contract)
converter.save("sales_agent_contract.owl")

# Use with Universal Agent Connector
# github.com/vpakspace/universal-agent-connector
```

### Microsoft Fabric IQ

```python
from powerbi_ontology.export import FabricIQExporter

exporter = FabricIQExporter(ontology)
fabric_json = exporter.export()

# Deploy as Ontology Item to OneLake
```

---

## 🧪 Testing

```bash
# Run all tests (340 tests, 82% coverage)
pytest

# Run with coverage report
pytest --cov=powerbi_ontology --cov-report=html

# Run specific test module
pytest tests/test_owl_exporter.py -v
```

**Test Statistics**:
- 340 tests passing
- 82% code coverage
- E2E tests with real .pbix files
- OntoGuard integration tests

---

## 📁 Project Structure

```
powerbi-ontology-extractor/
├── powerbi_ontology/
│   ├── __init__.py
│   ├── extractor.py           # PowerBIExtractor
│   ├── ontology_generator.py  # OntologyGenerator
│   ├── pbix_reader.py         # PBIXRay integration
│   ├── dax_parser.py          # DAX formula parsing
│   ├── semantic_debt.py       # Multi-dashboard analysis
│   ├── ontology_diff.py       # Diff & Merge
│   ├── review.py              # Collaborative review
│   ├── chat.py                # AI Chat (OpenAI)
│   ├── cli.py                 # CLI commands
│   ├── export/
│   │   ├── owl.py             # OWL/RDF export
│   │   ├── fabric_iq.py       # Fabric IQ export
│   │   ├── fabric_iq_to_owl.py
│   │   └── contract_to_owl.py
│   └── utils/
│       ├── visualizer.py
│       └── validators.py
├── ontology_editor.py         # Streamlit UI (1300+ lines)
├── examples/
│   ├── sample_pbix/           # Microsoft official samples
│   └── sample_ontology.json
├── tests/                     # 340 tests
├── requirements.txt
└── README.md
```

---

## 📊 Project Status

| Feature | Status | Coverage |
|---------|--------|----------|
| PBIX Extraction (PBIXRay) | ✅ Complete | 51% |
| DAX Parser | ✅ Complete | 73% |
| Ontology Generator | ✅ Complete | 83% |
| OWL Exporter | ✅ Complete | 95% |
| Fabric IQ Exporter | ✅ Complete | 97% |
| Contract Builder | ✅ Complete | 98% |
| Schema Drift Detection | ✅ Complete | 84% |
| Semantic Debt Analysis | ✅ Complete | 84% |
| Ontology Diff & Merge | ✅ Complete | 84% |
| Review Workflow | ✅ Complete | 93% |
| CLI Tool | ✅ Complete | 60% |
| Visual Editor (Streamlit) | ✅ Complete | - |
| AI Chat (OpenAI) | ✅ Complete | - |

**Overall**: 340 tests, 82% coverage

---

## 🛠️ Development Setup

```bash
# Clone repository
git clone https://github.com/vpakspace/powerbi-ontology-extractor.git
cd powerbi-ontology-extractor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Run tests
pytest

# Start Streamlit UI
streamlit run ontology_editor.py --server.port 8503
```

### Environment Variables

Create `.env` file for AI Chat:
```bash
# Required for Ontology Chat
OPENAI_API_KEY=your-openai-api-key

# Optional: Model selection (default: gpt-4o-mini)
# OPENAI_MODEL=gpt-4o-mini

# Optional: Local models via Ollama
# OLLAMA_BASE_URL=http://localhost:11434/v1
```

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Ways to contribute**:
- 🐛 Report bugs via [GitHub Issues](https://github.com/vpakspace/powerbi-ontology-extractor/issues)
- 💡 Suggest features
- 📝 Improve documentation
- 🔧 Submit pull requests
- ⭐ Star the repository

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🔗 Related Projects

| Project | Description |
|---------|-------------|
| [OntoGuard AI](https://github.com/vpakspace/ontoguard-ai) | Semantic Firewall for AI Agents |
| [Universal Agent Connector](https://github.com/vpakspace/universal-agent-connector) | MCP Infrastructure + Streamlit UI |

---

## 📞 Contact

- 🐛 **Issues**: [GitHub Issues](https://github.com/vpakspace/powerbi-ontology-extractor/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/vpakspace/powerbi-ontology-extractor/discussions)

---

<div align="center">

**Ready to unlock the semantic intelligence in your Power BI dashboards?** 🚀

```bash
git clone https://github.com/vpakspace/powerbi-ontology-extractor.git
cd powerbi-ontology-extractor
pip install -r requirements.txt
streamlit run ontology_editor.py
```

**Star ⭐ this repo if you find it useful!**

</div>
