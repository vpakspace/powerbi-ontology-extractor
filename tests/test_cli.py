"""
Tests for CLI module.

Tests command-line interface functionality:
- Extract command
- Batch command
- Analyze command
- Diff command
"""

import json
import pytest
from pathlib import Path
from click.testing import CliRunner

from powerbi_ontology.cli import (
    cli,
    _ontology_to_dict,
    _dict_to_ontology,
    _process_single_file,
)
from powerbi_ontology.ontology_generator import (
    Ontology,
    OntologyEntity,
    OntologyProperty,
    OntologyRelationship,
    BusinessRule,
)


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_ontology():
    """Create sample ontology for testing."""
    return Ontology(
        name="Test_Ontology",
        version="1.0",
        source="test.pbix",
        entities=[
            OntologyEntity(
                name="Customer",
                description="Customer entity",
                entity_type="dimension",
                properties=[
                    OntologyProperty(name="Id", data_type="Integer", required=True),
                    OntologyProperty(name="Name", data_type="String"),
                ],
                constraints=[],
            ),
        ],
        relationships=[
            OntologyRelationship(
                from_entity="Order",
                to_entity="Customer",
                from_property="CustomerId",
                to_property="Id",
                relationship_type="belongs_to",
                cardinality="many-to-one",
            ),
        ],
        business_rules=[
            BusinessRule(
                name="TestRule",
                entity="Customer",
                condition="Id > 0",
                action="Validate",
                classification="high",
            ),
        ],
        metadata={"author": "test"},
    )


class TestCLIHelp:
    """Tests for CLI help and version."""

    def test_help(self, runner):
        """Test help command."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "PowerBI Ontology Extractor" in result.output

    def test_version(self, runner):
        """Test version command."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_extract_help(self, runner):
        """Test extract command help."""
        result = runner.invoke(cli, ["extract", "--help"])
        assert result.exit_code == 0
        assert "--input" in result.output
        assert "--output" in result.output

    def test_batch_help(self, runner):
        """Test batch command help."""
        result = runner.invoke(cli, ["batch", "--help"])
        assert result.exit_code == 0
        assert "--workers" in result.output
        assert "--recursive" in result.output

    def test_analyze_help(self, runner):
        """Test analyze command help."""
        result = runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "--input" in result.output
        assert "--format" in result.output

    def test_diff_help(self, runner):
        """Test diff command help."""
        result = runner.invoke(cli, ["diff", "--help"])
        assert result.exit_code == 0
        assert "--source" in result.output
        assert "--target" in result.output


class TestOntologyConversion:
    """Tests for ontology serialization functions."""

    def test_ontology_to_dict(self, sample_ontology):
        """Test Ontology to dict conversion."""
        result = _ontology_to_dict(sample_ontology)

        assert result["name"] == "Test_Ontology"
        assert result["version"] == "1.0"
        assert len(result["entities"]) == 1
        assert len(result["relationships"]) == 1
        assert len(result["business_rules"]) == 1

    def test_dict_to_ontology(self, sample_ontology):
        """Test dict to Ontology conversion."""
        data = _ontology_to_dict(sample_ontology)
        result = _dict_to_ontology(data)

        assert result.name == sample_ontology.name
        assert result.version == sample_ontology.version
        assert len(result.entities) == len(sample_ontology.entities)
        assert len(result.relationships) == len(sample_ontology.relationships)
        assert len(result.business_rules) == len(sample_ontology.business_rules)

    def test_roundtrip_conversion(self, sample_ontology):
        """Test ontology conversion roundtrip."""
        data = _ontology_to_dict(sample_ontology)
        restored = _dict_to_ontology(data)
        data2 = _ontology_to_dict(restored)

        assert data == data2

    def test_dict_to_ontology_minimal(self):
        """Test conversion with minimal data."""
        data = {
            "name": "Minimal",
            "version": "1.0",
            "entities": [],
        }
        result = _dict_to_ontology(data)

        assert result.name == "Minimal"
        assert len(result.entities) == 0


class TestDiffCommand:
    """Tests for diff command."""

    def test_diff_identical_files(self, runner, sample_ontology, tmp_path):
        """Test diff with identical ontologies."""
        data = _ontology_to_dict(sample_ontology)
        source_file = tmp_path / "source.json"
        target_file = tmp_path / "target.json"

        source_file.write_text(json.dumps(data))
        target_file.write_text(json.dumps(data))

        result = runner.invoke(cli, [
            "diff",
            "--source", str(source_file),
            "--target", str(target_file),
        ])

        assert result.exit_code == 0
        assert "No changes" in result.output or "identical" in result.output.lower()

    def test_diff_with_changes(self, runner, sample_ontology, tmp_path):
        """Test diff with modified ontology."""
        source_data = _ontology_to_dict(sample_ontology)
        source_file = tmp_path / "source.json"
        source_file.write_text(json.dumps(source_data))

        target_data = _ontology_to_dict(sample_ontology)
        target_data["version"] = "2.0"
        target_data["entities"].append({
            "name": "Product",
            "description": "New entity",
            "entity_type": "dimension",
            "properties": [],
            "constraints": [],
        })
        target_file = tmp_path / "target.json"
        target_file.write_text(json.dumps(target_data))

        result = runner.invoke(cli, [
            "diff",
            "--source", str(source_file),
            "--target", str(target_file),
        ])

        assert result.exit_code == 0
        assert "Added" in result.output or "Product" in result.output

    def test_diff_json_format(self, runner, sample_ontology, tmp_path):
        """Test diff with JSON output format."""
        data = _ontology_to_dict(sample_ontology)
        source_file = tmp_path / "source.json"
        target_file = tmp_path / "target.json"

        source_file.write_text(json.dumps(data))
        target_file.write_text(json.dumps(data))

        result = runner.invoke(cli, [
            "diff",
            "--source", str(source_file),
            "--target", str(target_file),
            "--format", "json",
        ])

        assert result.exit_code == 0


class TestAnalyzeCommand:
    """Tests for analyze command."""

    def test_analyze_insufficient_files(self, runner, tmp_path):
        """Test analyze with only one file."""
        data = {"name": "Test", "version": "1.0", "entities": []}
        file1 = tmp_path / "test1.json"
        file1.write_text(json.dumps(data))

        result = runner.invoke(cli, [
            "analyze",
            "--input", str(tmp_path),
        ])

        assert result.exit_code == 0
        assert "at least 2" in result.output.lower()

    def test_analyze_no_conflicts(self, runner, sample_ontology, tmp_path):
        """Test analyze with non-conflicting ontologies."""
        data1 = _ontology_to_dict(sample_ontology)
        data1["name"] = "Ontology1"

        data2 = {
            "name": "Ontology2",
            "version": "1.0",
            "source": "test2.pbix",
            "entities": [
                {
                    "name": "Product",
                    "description": "",
                    "entity_type": "dimension",
                    "properties": [],
                    "constraints": [],
                }
            ],
            "relationships": [],
            "business_rules": [],
        }

        (tmp_path / "ont1.json").write_text(json.dumps(data1))
        (tmp_path / "ont2.json").write_text(json.dumps(data2))

        result = runner.invoke(cli, [
            "analyze",
            "--input", str(tmp_path),
        ])

        assert result.exit_code == 0


class TestBatchCommand:
    """Tests for batch command."""

    def test_batch_empty_directory(self, runner, tmp_path):
        """Test batch with no .pbix files."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = runner.invoke(cli, [
            "batch",
            "--input", str(tmp_path),
            "--output", str(output_dir),
        ])

        assert result.exit_code == 0
        assert "No files" in result.output

    def test_batch_creates_output_dir(self, runner, tmp_path):
        """Test that batch creates output directory."""
        output_dir = tmp_path / "new_output"

        result = runner.invoke(cli, [
            "batch",
            "--input", str(tmp_path),
            "--output", str(output_dir),
        ])

        assert output_dir.exists()


class TestExtractCommand:
    """Tests for extract command."""

    def test_extract_nonexistent_file(self, runner, tmp_path):
        """Test extract with nonexistent input file."""
        result = runner.invoke(cli, [
            "extract",
            "--input", str(tmp_path / "nonexistent.pbix"),
            "--output", str(tmp_path / "output.owl"),
        ])

        assert result.exit_code != 0


class TestProcessSingleFile:
    """Tests for _process_single_file helper."""

    def test_process_invalid_file(self, tmp_path):
        """Test processing invalid file."""
        fake_pbix = tmp_path / "fake.pbix"
        fake_pbix.write_text("not a real pbix file")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = _process_single_file(fake_pbix, output_dir, "json")

        assert result["success"] is False
        assert "error" in result
