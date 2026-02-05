"""
Tests for MCP Server.

Tests all MCP tools for PowerBI Ontology Extractor.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Test fixtures
SAMPLE_MODEL_DATA = {
    "name": "TestModel",
    "source_file": "test.pbix",
    "entities": [
        {
            "name": "Customer",
            "description": "Customer table",
            "source_table": "Customer",
            "primary_key": "CustomerID",
            "properties": [
                {
                    "name": "CustomerID",
                    "data_type": "Integer",
                    "required": True,
                    "unique": True,
                    "description": "Primary key",
                    "source_column": "CustomerID",
                },
                {
                    "name": "Name",
                    "data_type": "String",
                    "required": True,
                    "unique": False,
                    "description": "Customer name",
                    "source_column": "Name",
                },
            ],
        },
        {
            "name": "Sales",
            "description": "Sales table",
            "source_table": "Sales",
            "primary_key": "SalesID",
            "properties": [
                {
                    "name": "SalesID",
                    "data_type": "Integer",
                    "required": True,
                    "unique": True,
                    "description": "Primary key",
                    "source_column": "SalesID",
                },
                {
                    "name": "Amount",
                    "data_type": "Decimal",
                    "required": True,
                    "unique": False,
                    "description": "Sale amount",
                    "source_column": "Amount",
                },
            ],
        },
    ],
    "relationships": [
        {
            "from_entity": "Sales",
            "from_property": "CustomerID",
            "to_entity": "Customer",
            "to_property": "CustomerID",
            "cardinality": "many-to-one",
            "cross_filter_direction": "single",
            "is_active": True,
            "name": "Sales_Customer",
        }
    ],
    "measures": [
        {
            "name": "Total Sales",
            "dax_formula": "SUM(Sales[Amount])",
            "description": "Sum of sales",
            "folder": "",
            "table": "Sales",
            "dependencies": ["Sales.Amount"],
        }
    ],
    "hierarchies": [],
    "security_rules": [],
    "metadata": {"test": True},
}

SAMPLE_ONTOLOGY_DATA = {
    "name": "TestOntology",
    "version": "1.0.0",
    "source": "test.pbix",
    "entities": [
        {
            "name": "Customer",
            "description": "Customer entity",
            "entity_type": "standard",
            "source_table": "Customer",
            "properties": [
                {
                    "name": "CustomerID",
                    "data_type": "Integer",
                    "required": True,
                    "unique": True,
                    "description": "Primary key",
                    "source_column": "CustomerID",
                    "constraints": [],
                }
            ],
            "constraints": [],
        },
        {
            "name": "Sales",
            "description": "Sales entity",
            "entity_type": "fact",
            "source_table": "Sales",
            "properties": [
                {
                    "name": "Amount",
                    "data_type": "Decimal",
                    "required": True,
                    "unique": False,
                    "description": "Sale amount",
                    "source_column": "Amount",
                    "constraints": [],
                }
            ],
            "constraints": [],
        },
    ],
    "relationships": [
        {
            "from_entity": "Sales",
            "from_property": "CustomerID",
            "to_entity": "Customer",
            "to_property": "CustomerID",
            "relationship_type": "belongs_to",
            "cardinality": "many-to-one",
            "description": "Sales to Customer",
            "source_relationship": "Sales_Customer",
        }
    ],
    "business_rules": [
        {
            "name": "TotalSalesRule",
            "entity": "Sales",
            "condition": "SUM(Sales[Amount])",
            "action": "calculate",
            "classification": "measure",
            "description": "Total sales calculation",
            "priority": 1,
            "source_measure": "Total Sales",
        }
    ],
    "metadata": {"test": True},
}


class TestMCPConfig:
    """Test MCP configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        from powerbi_ontology.mcp_config import MCPConfig, DEFAULT_CONFIG

        config = MCPConfig()

        assert config.server_name == DEFAULT_CONFIG["server"]["name"]
        assert config.log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]
        assert config.include_measures is True
        assert config.include_security is True
        assert "Admin" in config.default_roles

    def test_get_config_value(self):
        """Test getting config values by key."""
        from powerbi_ontology.mcp_config import MCPConfig

        config = MCPConfig()

        assert config.get("server.name") is not None
        assert config.get("nonexistent", "default") == "default"

    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        from powerbi_ontology.mcp_config import MCPConfig

        config = MCPConfig()
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert "server" in config_dict
        assert "extraction" in config_dict


class TestMCPModels:
    """Test MCP Pydantic models."""

    def test_extract_result(self):
        """Test ExtractResult model."""
        from powerbi_ontology.mcp_models import ExtractResult

        result = ExtractResult(
            success=True,
            entities_count=5,
            relationships_count=3,
        )

        assert result.success is True
        assert result.entities_count == 5

        result_dict = result.to_dict()
        assert result_dict["success"] is True

    def test_generate_result(self):
        """Test GenerateResult model."""
        from powerbi_ontology.mcp_models import GenerateResult

        result = GenerateResult(
            success=True,
            patterns_detected=["date_table: Calendar"],
        )

        assert len(result.patterns_detected) == 1

    def test_diff_result(self):
        """Test DiffResult model."""
        from powerbi_ontology.mcp_models import DiffResult

        result = DiffResult(
            success=True,
            has_changes=True,
            total_changes=5,
            added=2,
            removed=1,
            modified=2,
        )

        assert result.total_changes == 5
        assert result.added + result.removed + result.modified == 5


class TestOntologyGenerate:
    """Test ontology generation tool."""

    def test_generate_from_model_data(self):
        """Test generating ontology from model data."""
        from powerbi_ontology.mcp_server import _ontology_generate_impl

        result = _ontology_generate_impl(SAMPLE_MODEL_DATA)

        assert result["success"] is True
        assert "ontology_data" in result
        assert len(result["ontology_data"]["entities"]) == 2

    def test_generate_with_patterns(self):
        """Test pattern detection during generation."""
        from powerbi_ontology.mcp_server import _ontology_generate_impl

        result = _ontology_generate_impl(SAMPLE_MODEL_DATA, detect_patterns=True)

        assert result["success"] is True
        assert "patterns_detected" in result

    def test_generate_empty_model(self):
        """Test generating from empty model."""
        from powerbi_ontology.mcp_server import _ontology_generate_impl

        empty_model = {"name": "Empty", "entities": [], "relationships": [], "measures": []}
        result = _ontology_generate_impl(empty_model)

        assert result["success"] is True
        assert len(result["ontology_data"]["entities"]) == 0


class TestExportOWL:
    """Test OWL export tool."""

    def test_export_xml(self):
        """Test exporting to XML format."""
        from powerbi_ontology.mcp_server import _export_owl_impl

        result = _export_owl_impl(SAMPLE_ONTOLOGY_DATA, format="xml")

        assert result["success"] is True
        assert "owl_content" in result
        assert "<?xml" in result["owl_content"] or "<rdf:RDF" in result["owl_content"]

    def test_export_turtle(self):
        """Test exporting to Turtle format."""
        from powerbi_ontology.mcp_server import _export_owl_impl

        result = _export_owl_impl(SAMPLE_ONTOLOGY_DATA, format="turtle")

        assert result["success"] is True
        assert "owl_content" in result

    def test_export_with_action_rules(self):
        """Test exporting with action rules."""
        from powerbi_ontology.mcp_server import _export_owl_impl

        result = _export_owl_impl(SAMPLE_ONTOLOGY_DATA, include_action_rules=True)

        assert result["success"] is True
        assert "summary" in result
        # Action rules should create additional triples
        assert result["summary"]["action_rules"] > 0

    def test_export_without_action_rules(self):
        """Test exporting without action rules."""
        from powerbi_ontology.mcp_server import _export_owl_impl

        result = _export_owl_impl(SAMPLE_ONTOLOGY_DATA, include_action_rules=False)

        assert result["success"] is True


class TestExportJSON:
    """Test JSON export tool."""

    def test_export_json_content(self):
        """Test exporting JSON content."""
        from powerbi_ontology.mcp_server import _export_json_impl

        result = _export_json_impl(SAMPLE_ONTOLOGY_DATA)

        assert result["success"] is True
        assert "json_content" in result

        # Verify it's valid JSON
        parsed = json.loads(result["json_content"])
        assert parsed["name"] == "TestOntology"

    def test_export_json_to_file(self, tmp_path):
        """Test exporting JSON to file."""
        from powerbi_ontology.mcp_server import _export_json_impl

        output_path = str(tmp_path / "output.json")
        result = _export_json_impl(SAMPLE_ONTOLOGY_DATA, output_path=output_path)

        assert result["success"] is True
        assert result["output_path"] == output_path
        assert Path(output_path).exists()


class TestAnalyzeDebt:
    """Test semantic debt analysis tool."""

    def test_analyze_two_ontologies(self):
        """Test analyzing two ontologies."""
        from powerbi_ontology.mcp_server import _analyze_debt_impl

        # Create two ontologies with a conflict
        ont1 = SAMPLE_ONTOLOGY_DATA.copy()
        ont1["name"] = "Sales"

        ont2 = SAMPLE_ONTOLOGY_DATA.copy()
        ont2["name"] = "Finance"
        # Modify to create conflict
        ont2["entities"] = [
            {
                "name": "Customer",
                "description": "Different description",
                "entity_type": "dimension",  # Different type
                "source_table": "Customers",  # Different source
                "properties": [
                    {
                        "name": "ID",  # Different property name
                        "data_type": "String",  # Different type!
                        "required": False,
                        "unique": False,
                        "description": "",
                        "source_column": "ID",
                        "constraints": [],
                    }
                ],
                "constraints": [],
            }
        ]

        result = _analyze_debt_impl({
            "Sales.pbix": ont1,
            "Finance.pbix": ont2,
        })

        assert result["success"] is True
        assert "total_conflicts" in result

    def test_analyze_insufficient_ontologies(self):
        """Test error when less than 2 ontologies."""
        from powerbi_ontology.mcp_server import _analyze_debt_impl

        result = _analyze_debt_impl({"single": SAMPLE_ONTOLOGY_DATA})

        assert result["success"] is False
        assert "at least 2" in result["error"]


class TestOntologyDiff:
    """Test ontology diff tool."""

    def test_diff_identical(self):
        """Test diffing identical ontologies."""
        from powerbi_ontology.mcp_server import _ontology_diff_impl

        result = _ontology_diff_impl(SAMPLE_ONTOLOGY_DATA, SAMPLE_ONTOLOGY_DATA)

        assert result["success"] is True
        assert result["has_changes"] is False
        assert result["total_changes"] == 0

    def test_diff_with_changes(self):
        """Test diffing ontologies with changes."""
        from powerbi_ontology.mcp_server import _ontology_diff_impl

        # Create modified version
        modified = json.loads(json.dumps(SAMPLE_ONTOLOGY_DATA))
        modified["entities"].append({
            "name": "NewEntity",
            "description": "Added entity",
            "entity_type": "standard",
            "source_table": "New",
            "properties": [],
            "constraints": [],
        })

        result = _ontology_diff_impl(SAMPLE_ONTOLOGY_DATA, modified)

        assert result["success"] is True
        assert result["has_changes"] is True
        assert result["added"] > 0

    def test_diff_generates_changelog(self):
        """Test that diff generates changelog."""
        from powerbi_ontology.mcp_server import _ontology_diff_impl

        modified = json.loads(json.dumps(SAMPLE_ONTOLOGY_DATA))
        modified["version"] = "2.0.0"

        result = _ontology_diff_impl(SAMPLE_ONTOLOGY_DATA, modified)

        assert result["success"] is True
        assert "changelog" in result
        assert len(result["changelog"]) > 0


class TestOntologyMerge:
    """Test ontology merge tool."""

    def test_merge_no_conflicts(self):
        """Test merging ontologies without conflicts."""
        from powerbi_ontology.mcp_server import _ontology_merge_impl

        base = SAMPLE_ONTOLOGY_DATA

        # Ours adds an entity
        ours = json.loads(json.dumps(base))
        ours["entities"].append({
            "name": "OurEntity",
            "description": "Our addition",
            "entity_type": "standard",
            "source_table": "Our",
            "properties": [],
            "constraints": [],
        })

        # Theirs adds a different entity
        theirs = json.loads(json.dumps(base))
        theirs["entities"].append({
            "name": "TheirEntity",
            "description": "Their addition",
            "entity_type": "standard",
            "source_table": "Their",
            "properties": [],
            "constraints": [],
        })

        result = _ontology_merge_impl(base, ours, theirs)

        assert result["success"] is True
        assert "merged_ontology" in result

    def test_merge_with_strategy(self):
        """Test merge with different strategies."""
        from powerbi_ontology.mcp_server import _ontology_merge_impl

        base = SAMPLE_ONTOLOGY_DATA
        ours = json.loads(json.dumps(base))
        theirs = json.loads(json.dumps(base))

        for strategy in ["ours", "theirs"]:
            result = _ontology_merge_impl(base, ours, theirs, strategy=strategy)
            assert result["success"] is True


class TestOntologyChatAsk:
    """Test chat tool."""

    def test_chat_without_api_key(self):
        """Test chat fails gracefully without API key."""
        from powerbi_ontology.mcp_server import _ontology_chat_ask_impl

        # Ensure no API key
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
            result = _ontology_chat_ask_impl(
                "What entities are there?",
                SAMPLE_ONTOLOGY_DATA,
            )

            assert result["success"] is False
            assert "OPENAI_API_KEY" in result["error"]

    @patch("powerbi_ontology.chat.OntologyChat")
    def test_chat_with_mock(self, mock_chat_class):
        """Test chat with mocked OpenAI."""
        from powerbi_ontology.mcp_server import _ontology_chat_ask_impl

        # Setup mock
        mock_instance = MagicMock()
        mock_instance.ask.return_value = "There are 2 entities: Customer and Sales"
        mock_instance.get_suggestions.return_value = ["What are the relationships?"]
        mock_chat_class.return_value = mock_instance

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            result = _ontology_chat_ask_impl(
                "What entities are there?",
                SAMPLE_ONTOLOGY_DATA,
            )

            assert result["success"] is True
            assert "entities" in result["answer"].lower()


class TestPbixExtract:
    """Test pbix extraction tool."""

    def test_extract_file_not_found(self):
        """Test extraction with non-existent file."""
        from powerbi_ontology.mcp_server import _pbix_extract_impl

        result = _pbix_extract_impl("/nonexistent/path/file.pbix")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_extract_invalid_extension(self, tmp_path):
        """Test extraction with wrong file extension."""
        from powerbi_ontology.mcp_server import _pbix_extract_impl

        # Create a non-pbix file
        test_file = tmp_path / "test.txt"
        test_file.write_text("not a pbix file")

        result = _pbix_extract_impl(str(test_file))

        assert result["success"] is False
        assert "invalid file type" in result["error"].lower()


class TestHelperFunctions:
    """Test helper functions."""

    def test_ontology_to_dict(self):
        """Test converting Ontology to dict."""
        from powerbi_ontology.mcp_server import _ontology_to_dict, _dict_to_ontology

        # Convert to ontology and back
        ontology = _dict_to_ontology(SAMPLE_ONTOLOGY_DATA)
        result = _ontology_to_dict(ontology)

        assert result["name"] == SAMPLE_ONTOLOGY_DATA["name"]
        assert len(result["entities"]) == len(SAMPLE_ONTOLOGY_DATA["entities"])

    def test_dict_to_ontology(self):
        """Test converting dict to Ontology."""
        from powerbi_ontology.mcp_server import _dict_to_ontology

        ontology = _dict_to_ontology(SAMPLE_ONTOLOGY_DATA)

        assert ontology.name == "TestOntology"
        assert len(ontology.entities) == 2
        assert len(ontology.relationships) == 1


class TestIntegration:
    """Integration tests for MCP tools pipeline."""

    def test_generate_and_export_pipeline(self):
        """Test full pipeline: generate -> export."""
        from powerbi_ontology.mcp_server import (
            _ontology_generate_impl,
            _export_owl_impl,
            _export_json_impl,
        )

        # Generate
        gen_result = _ontology_generate_impl(SAMPLE_MODEL_DATA)
        assert gen_result["success"] is True

        ontology_data = gen_result["ontology_data"]

        # Export OWL
        owl_result = _export_owl_impl(ontology_data)
        assert owl_result["success"] is True
        assert len(owl_result["owl_content"]) > 100

        # Export JSON
        json_result = _export_json_impl(ontology_data)
        assert json_result["success"] is True

    def test_diff_and_merge_pipeline(self):
        """Test diff -> merge pipeline."""
        from powerbi_ontology.mcp_server import (
            _ontology_diff_impl,
            _ontology_merge_impl,
        )

        base = SAMPLE_ONTOLOGY_DATA

        # Create versions
        v1 = json.loads(json.dumps(base))
        v1["version"] = "1.1.0"

        v2 = json.loads(json.dumps(base))
        v2["version"] = "1.2.0"

        # Diff
        diff_result = _ontology_diff_impl(v1, v2)
        assert diff_result["success"] is True

        # Merge
        merge_result = _ontology_merge_impl(base, v1, v2)
        assert merge_result["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
