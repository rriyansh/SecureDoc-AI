"""CLI entry point."""

import typer
import json
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.ingest import ingest, build_index, IngestionResult
from src.rag_pipeline import SecureRAGPipeline
from src.evaluate import run_evaluation, create_eval_dataset
from src.config import config
from src.logger import get_logger

app = typer.Typer(help="SecureDoc AI CLI", rich_markup_mode="rich")
console = Console()
logger = get_logger(__name__)


@app.command()
def ingest(
    doc_dir: str = typer.Option("documents", "--dir", "-d", help="Document directory"),
    user_id: str = typer.Option("cli-user", "--user", "-u", help="User ID for audit"),
):
    """Ingest documents into the vector store."""
    console.print(f"[bold blue]Ingesting documents from {doc_dir}...[/bold blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing documents...", total=None)
        result: IngestionResult = ingest(doc_dir=doc_dir, user_id=user_id)
        progress.update(task, completed=True)

    # Display results
    table = Table(title="Ingestion Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Documents Processed", str(result.documents_processed))
    table.add_row("Chunks Created", str(result.chunks_created))
    table.add_row("Duration", f"{result.duration_ms:.1f}ms")
    table.add_row("PII Detected", "Yes" if result.pii_detected else "No")
    table.add_row("Errors", str(len(result.errors)))

    console.print(table)

    if result.errors:
        console.print("[bold red]Errors:[/bold red]")
        for error in result.errors:
            console.print(f"  - {error}")


@app.command()
def build_index(
    doc_dir: str = typer.Option("documents", "--dir", "-d", help="Document directory"),
    collection: str = typer.Option(None, "--collection", "-c", help="Vector collection name"),
    user_id: str = typer.Option("cli-user", "--user", "-u", help="User ID for audit"),
):
    """Build vector index from documents."""
    console.print(f"[bold blue]Building vector index from {doc_dir}...[/bold blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Building index...", total=None)
        result = build_index(doc_dir=doc_dir, user_id=user_id)
        progress.update(task, completed=True)

    console.print(f"[green]Index built: {result.chunks_created} chunks indexed[/green]")


@app.command()
def query(
    question: str = typer.Argument(..., help="Question to ask"),
    user_id: str = typer.Option("cli-user", "--user", "-u", help="User ID for audit"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable cache"),
    no_rewrite: bool = typer.Option(False, "--no-rewrite", help="Disable query rewriting"),
    show_sources: bool = typer.Option(False, "--sources", "-s", help="Show source documents"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text, json"),
):
    """Ask a question through the RAG pipeline."""
    pipeline = SecureRAGPipeline()

    console.print(f"[bold blue]Query:[/bold blue] {question}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing query...", total=None)
        answer = pipeline.query(
            question=question,
            user_id=user_id,
            use_cache=not no_cache,
            use_rewrite=not no_rewrite,
        )
        progress.update(task, completed=True)

    if format == "json":
        console.print(json.dumps({"question": question, "answer": answer}, indent=2))
    else:
        console.print(f"\n[bold green]Answer:[/bold green]\n{answer}")


@app.command()
def eval(
    dataset: str = typer.Option(None, "--dataset", "-d", help="Evaluation dataset path"),
    output: str = typer.Option("tests/eval_results.json", "--output", "-o", help="Output path"),
    user_id: str = typer.Option("cli-user", "--user", "-u", help="User ID for audit"),
):
    """Run RAGAS evaluation."""
    console.print("[bold blue]Running RAGAS evaluation...[/bold blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Evaluating...", total=None)
        results = run_evaluation(dataset_path=dataset, output_path=output, user_id=user_id)
        progress.update(task, completed=True)

    if "error" in results:
        console.print(f"[bold red]Evaluation failed:[/bold red] {results['error']}")
        return

    table = Table(title="Evaluation Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Score", style="green")

    for metric, score in results.get("metrics", {}).items():
        table.add_row(metric, f"{score:.3f}")

    table.add_row("Duration", f"{results.get('duration_seconds', 0):.1f}s")
    console.print(table)
    console.print(f"\nResults saved to: {output}")


@app.command()
def create_eval_dataset(
    output: str = typer.Option("tests/eval_dataset.json", "--output", "-o", help="Output path"),
):
    """Create a sample evaluation dataset."""
    questions = [
        "What is the data encryption policy?",
        "How long are documents retained?",
        "What are the MFA requirements?",
        "How should security incidents be reported?",
    ]
    ground_truths = [
        "All enterprise documents must be encrypted at rest and in transit.",
        "Documents are retained for a period of 7 years unless otherwise specified by legal requirements.",
        "Multi-factor authentication is required for all users accessing the document management system.",
        "Security incidents must be reported to the IT security team within 24 hours of discovery.",
    ]
    contexts = [
        ["All enterprise documents must be encrypted at rest and in transit. Access to sensitive data is restricted to authorized personnel only."],
        ["Documents are retained for a period of 7 years unless otherwise specified by legal requirements."],
        ["Multi-factor authentication is required for all users accessing the document management system."],
        ["Security incidents must be reported to the IT security team within 24 hours of discovery."],
    ]

    create_eval_dataset(questions, ground_truths, contexts, output)
    console.print(f"[green]Created evaluation dataset at {output}[/green]")


@app.command()
def config_show():
    """Show current configuration."""
    from src.config import config as config_obj
    from src.security import sanitize_dict

    sanitized = sanitize_dict(config_obj._data)
    console.print(json.dumps(sanitized, indent=2))


@app.command()
def version():
    """Show version information."""
    console.print("SecureDoc AI v0.1.0")


if __name__ == "__main__":
    app()