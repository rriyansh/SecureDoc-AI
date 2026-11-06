"""CLI entry point."""

import typer

app = typer.Typer(help="SecureDoc AI CLI")


@app.command()
def ingest():
    """Ingest documents into the vector store."""
    from src.ingest import ingest

    ingest()


@app.command()
def query(question: str):
    """Ask a question through the RAG pipeline."""
    from src.rag_pipeline import SecureRAGPipeline

    pipeline = SecureRAGPipeline()
    answer = pipeline.query(question)
    typer.echo(answer)


@app.command()
def eval():
    """Run RAGAS evaluation."""
    from src.evaluate import run_evaluation

    run_evaluation()


if __name__ == "__main__":
    app()
