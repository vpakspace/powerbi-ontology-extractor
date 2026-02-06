"""
CLI for PowerBI Ontology Extractor.

Provides command-line interface for:
- Extracting ontologies from .pbix files
- Batch processing directories
- Exporting to various formats (OWL, JSON)
- Semantic debt analysis
- Ontology diff

Usage:
    pbix2owl extract --input file.pbix --output ontology.owl
    pbix2owl batch --input ./dashboards/ --output ./ontologies/
    pbix2owl analyze --input ./ontologies/ --output report.md
    pbix2owl diff --source v1.json --target v2.json
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel

from powerbi_ontology.extractor import PowerBIExtractor
from powerbi_ontology.ontology_generator import OntologyGenerator, Ontology
from powerbi_ontology.export.owl import OWLExporter
from powerbi_ontology.semantic_debt import SemanticDebtAnalyzer
from powerbi_ontology.ontology_diff import OntologyDiff

console = Console()
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@click.group()
@click.version_option(version="0.1.1", prog_name="pbix2owl")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def cli(verbose: bool):
    """PowerBI Ontology Extractor - Extract semantic intelligence from Power BI files."""
    setup_logging(verbose)


@cli.command()
@click.option("-i", "--input", "input_path", required=True, type=click.Path(exists=True), help="Input .pbix file")
@click.option("-o", "--output", "output_path", required=True, type=click.Path(), help="Output file (OWL or JSON)")
@click.option("-f", "--format", "output_format", type=click.Choice(["owl", "json"]), default="owl", help="Output format")
@click.option("--include-rules/--no-rules", default=True, help="Include action rules in OWL")
@click.option("--include-constraints/--no-constraints", default=True, help="Include constraints in OWL")
def extract(input_path: str, output_path: str, output_format: str, include_rules: bool, include_constraints: bool):
    """Extract ontology from a single .pbix file."""
    input_file = Path(input_path)
    output_file = Path(output_path)

    with console.status(f"[bold green]Processing {input_file.name}..."):
        try:
            # Extract semantic model
            extractor = PowerBIExtractor(str(input_file))
            semantic_model = extractor.extract()

            # Generate ontology
            generator = OntologyGenerator(semantic_model)
            ontology = generator.generate()

            # Export
            if output_format == "owl":
                owl_exporter = OWLExporter(
                    ontology,
                    include_action_rules=include_rules,
                    include_constraints=include_constraints,
                )
                owl_exporter.save(str(output_file))
            else:
                # JSON export
                with open(output_file, "w") as f:
                    json.dump(_ontology_to_dict(ontology), f, indent=2)

            console.print(f"[green]✓[/green] Exported to {output_file}")

            # Show summary
            _show_extraction_summary(ontology)

        except Exception as e:
            console.print(f"[red]✗ Error:[/red] {e}")
            raise click.Abort()


@cli.command()
@click.option("-i", "--input", "input_dir", required=True, type=click.Path(exists=True), help="Input directory with .pbix files")
@click.option("-o", "--output", "output_dir", required=True, type=click.Path(), help="Output directory for ontologies")
@click.option("-f", "--format", "output_format", type=click.Choice(["owl", "json"]), default="owl", help="Output format")
@click.option("-w", "--workers", default=4, help="Number of parallel workers")
@click.option("--pattern", default="*.pbix", help="File pattern to match")
@click.option("--recursive/--no-recursive", default=False, help="Search recursively")
def batch(input_dir: str, output_dir: str, output_format: str, workers: int, pattern: str, recursive: bool):
    """Batch process multiple .pbix files."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Find files
    if recursive:
        files = list(input_path.rglob(pattern))
    else:
        files = list(input_path.glob(pattern))

    if not files:
        console.print(f"[yellow]No files matching '{pattern}' found in {input_dir}[/yellow]")
        return

    console.print(f"[bold]Found {len(files)} files to process[/bold]\n")

    results = {"success": [], "failed": []}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing files...", total=len(files))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_process_single_file, f, output_path, output_format): f
                for f in files
            }

            for future in as_completed(futures):
                file = futures[future]
                try:
                    result = future.result()
                    if result["success"]:
                        results["success"].append(result)
                    else:
                        results["failed"].append(result)
                except Exception as e:
                    results["failed"].append({"file": str(file), "error": str(e)})

                progress.advance(task)

    # Show results
    _show_batch_results(results)


@cli.command()
@click.option("-i", "--input", "input_dir", required=True, type=click.Path(exists=True), help="Directory with ontology files")
@click.option("-o", "--output", "output_path", type=click.Path(), help="Output report file")
@click.option("-f", "--format", "output_format", type=click.Choice(["markdown", "json"]), default="markdown", help="Report format")
@click.option("--pattern", default="*.json", help="File pattern to match")
def analyze(input_dir: str, output_path: Optional[str], output_format: str, pattern: str):
    """Analyze semantic debt across multiple ontologies."""
    input_path = Path(input_dir)
    files = list(input_path.glob(pattern))

    if len(files) < 2:
        console.print("[yellow]Need at least 2 ontology files for analysis[/yellow]")
        return

    console.print(f"[bold]Analyzing {len(files)} ontologies...[/bold]\n")

    analyzer = SemanticDebtAnalyzer()

    with console.status("[bold green]Loading ontologies..."):
        for file in files:
            try:
                with open(file) as f:
                    data = json.load(f)
                ontology = _dict_to_ontology(data)
                analyzer.add_ontology(file.name, ontology)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load {file.name}: {e}[/yellow]")

    report = analyzer.analyze()

    # Output report
    if output_format == "markdown":
        content = report.to_markdown()
    else:
        content = json.dumps(report.to_dict(), indent=2)

    if output_path:
        Path(output_path).write_text(content)
        console.print(f"[green]✓[/green] Report saved to {output_path}")
    else:
        console.print(content)

    # Show summary panel
    _show_analysis_summary(report)


@cli.command()
@click.option("-s", "--source", required=True, type=click.Path(exists=True), help="Source ontology file")
@click.option("-t", "--target", required=True, type=click.Path(exists=True), help="Target ontology file")
@click.option("-o", "--output", "output_path", type=click.Path(), help="Output diff file")
@click.option("-f", "--format", "output_format", type=click.Choice(["changelog", "unified", "json"]), default="changelog", help="Output format")
def diff(source: str, target: str, output_path: Optional[str], output_format: str):
    """Compare two ontology versions."""
    source_path = Path(source)
    target_path = Path(target)

    with console.status("[bold green]Comparing ontologies..."):
        # Load ontologies
        with open(source_path) as f:
            source_data = json.load(f)
        with open(target_path) as f:
            target_data = json.load(f)

        source_ont = _dict_to_ontology(source_data)
        target_ont = _dict_to_ontology(target_data)

        # Perform diff
        differ = OntologyDiff(source_ont, target_ont)
        report = differ.diff()

    # Output
    if output_format == "changelog":
        content = report.to_changelog()
    elif output_format == "unified":
        content = report.to_unified_diff()
    else:
        content = json.dumps(report.to_dict(), indent=2)

    if output_path:
        Path(output_path).write_text(content)
        console.print(f"[green]✓[/green] Diff saved to {output_path}")
    else:
        console.print(content)

    # Show summary
    _show_diff_summary(report)


def _process_single_file(file: Path, output_dir: Path, output_format: str) -> dict:
    """Process a single .pbix file."""
    try:
        extractor = PowerBIExtractor(str(file))
        semantic_model = extractor.extract()

        generator = OntologyGenerator(semantic_model)
        ontology = generator.generate()

        # Determine output filename
        output_name = file.stem + (".owl" if output_format == "owl" else ".json")
        output_file = output_dir / output_name

        if output_format == "owl":
            owl_exporter = OWLExporter(ontology)
            owl_exporter.save(str(output_file))
        else:
            with open(output_file, "w") as f:
                json.dump(_ontology_to_dict(ontology), f, indent=2)

        return {
            "success": True,
            "file": str(file),
            "output": str(output_file),
            "entities": len(ontology.entities),
            "relationships": len(ontology.relationships),
        }

    except Exception as e:
        return {
            "success": False,
            "file": str(file),
            "error": str(e),
        }


def _ontology_to_dict(ontology: Ontology) -> dict:
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
                "properties": [
                    {
                        "name": p.name,
                        "data_type": p.data_type,
                        "required": p.required,
                        "unique": p.unique,
                        "description": p.description,
                        "constraints": [
                            {"type": c.type, "value": c.value, "message": c.message}
                            for c in (p.constraints or [])
                        ],
                    }
                    for p in e.properties
                ],
                "constraints": [],
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
                "name": r.name,
                "entity": r.entity,
                "condition": r.condition,
                "action": r.action,
                "classification": r.classification,
                "description": r.description,
                "priority": r.priority,
            }
            for r in ontology.business_rules
        ],
        "metadata": ontology.metadata or {},
    }


def _dict_to_ontology(data: dict) -> Ontology:
    """Convert dictionary to Ontology."""
    from powerbi_ontology.ontology_generator import (
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


def _show_extraction_summary(ontology: Ontology):
    """Display extraction summary."""
    table = Table(title="Extraction Summary", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Ontology Name", ontology.name)
    table.add_row("Version", ontology.version)
    table.add_row("Entities", str(len(ontology.entities)))
    table.add_row("Relationships", str(len(ontology.relationships)))
    table.add_row("Business Rules", str(len(ontology.business_rules)))

    total_props = sum(len(e.properties) for e in ontology.entities)
    table.add_row("Total Properties", str(total_props))

    console.print(table)


def _show_batch_results(results: dict):
    """Display batch processing results."""
    console.print()

    # Success table
    if results["success"]:
        table = Table(title=f"[green]✓ Successfully Processed ({len(results['success'])} files)[/green]")
        table.add_column("File", style="cyan")
        table.add_column("Entities", justify="right")
        table.add_column("Relationships", justify="right")
        table.add_column("Output")

        for r in results["success"]:
            table.add_row(
                Path(r["file"]).name,
                str(r.get("entities", 0)),
                str(r.get("relationships", 0)),
                Path(r["output"]).name,
            )

        console.print(table)

    # Failure table
    if results["failed"]:
        console.print()
        table = Table(title=f"[red]✗ Failed ({len(results['failed'])} files)[/red]")
        table.add_column("File", style="cyan")
        table.add_column("Error", style="red")

        for r in results["failed"]:
            table.add_row(
                Path(r["file"]).name,
                r.get("error", "Unknown error")[:60],
            )

        console.print(table)

    # Summary panel
    total = len(results["success"]) + len(results["failed"])
    success_rate = len(results["success"]) / total * 100 if total > 0 else 0

    console.print()
    console.print(Panel(
        f"[bold]Total:[/bold] {total} files\n"
        f"[green]Success:[/green] {len(results['success'])}\n"
        f"[red]Failed:[/red] {len(results['failed'])}\n"
        f"[cyan]Success Rate:[/cyan] {success_rate:.1f}%",
        title="Batch Summary",
    ))


def _show_analysis_summary(report):
    """Display semantic debt analysis summary."""
    console.print()

    if not report.conflicts:
        console.print(Panel(
            "[green]No semantic conflicts detected![/green]\n"
            "All ontologies are semantically consistent.",
            title="Analysis Result",
        ))
        return

    summary = report.summary
    console.print(Panel(
        f"[bold]Total Conflicts:[/bold] {summary.get('total_conflicts', 0)}\n"
        f"[red]🔴 Critical:[/red] {summary.get('critical', 0)}\n"
        f"[yellow]🟡 Warning:[/yellow] {summary.get('warning', 0)}\n"
        f"[blue]🔵 Info:[/blue] {summary.get('info', 0)}",
        title="Semantic Debt Summary",
    ))


def _show_diff_summary(report):
    """Display diff summary."""
    console.print()

    if not report.has_changes():
        console.print(Panel(
            "[green]No changes detected![/green]\n"
            "Ontologies are identical.",
            title="Diff Result",
        ))
        return

    summary = report.summary
    console.print(Panel(
        f"[bold]Total Changes:[/bold] {summary.get('total_changes', 0)}\n"
        f"[green]➕ Added:[/green] {summary.get('added', 0)}\n"
        f"[red]➖ Removed:[/red] {summary.get('removed', 0)}\n"
        f"[yellow]📝 Modified:[/yellow] {summary.get('modified', 0)}",
        title="Diff Summary",
    ))


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
