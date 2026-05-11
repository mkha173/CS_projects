"""Command-line interface for the personal RAG."""
from __future__ import annotations

from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from rag.chat import Chat
from rag.ingest import build_chunks, iter_documents
from rag.store import VectorStore

load_dotenv()
console = Console()


@click.group()
def cli() -> None:
    """Chat with your notes, powered by Claude."""


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--chunk-size", default=800, show_default=True, help="Target chunk size in characters.")
@click.option("--overlap", default=100, show_default=True, help="Character overlap between chunks.")
def ingest(path: Path, chunk_size: int, overlap: int) -> None:
    """Add files or folders to the index."""
    docs = list(iter_documents(path))
    if not docs:
        console.print(f"[yellow]No supported documents found under {path}[/yellow]")
        return

    console.print(f"Reading [bold]{len(docs)}[/bold] document(s)...")
    chunks = build_chunks(docs, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        console.print("[yellow]No text extracted.[/yellow]")
        return

    console.print(f"Embedding [bold]{len(chunks)}[/bold] chunk(s) and saving to the store...")
    store = VectorStore()
    added = store.add_chunks(chunks)
    stats = store.stats()
    console.print(
        f"[green]OK[/green] - added {added} chunks. "
        f"Collection [bold]{stats['collection']}[/bold] now holds {stats['count']} chunks."
    )


@cli.command()
def stats() -> None:
    """Show what's in the index."""
    store = VectorStore()
    s = store.stats()
    table = Table(title="RAG store")
    table.add_column("key")
    table.add_column("value")
    for k, v in s.items():
        table.add_row(str(k), str(v))
    console.print(table)


@cli.command()
@click.confirmation_option(prompt="Wipe the entire index?")
def reset() -> None:
    """Delete every document from the index."""
    store = VectorStore()
    store.reset()
    console.print("[green]Index cleared.[/green]")


def _render_answer(answer) -> None:
    console.print(Panel(Markdown(answer.text), title="answer", border_style="cyan"))
    if answer.hits:
        table = Table(title="sources", show_lines=False)
        table.add_column("#", style="dim")
        table.add_column("file")
        table.add_column("chunk", justify="right")
        table.add_column("distance", justify="right")
        for i, h in enumerate(answer.hits, start=1):
            table.add_row(
                str(i),
                Path(h.source).name,
                str(h.chunk_index),
                f"{h.distance:.3f}",
            )
        console.print(table)


@cli.command()
@click.argument("question", nargs=-1, required=True)
@click.option("-k", "top_k", default=5, show_default=True, help="How many chunks to retrieve.")
def ask(question: tuple[str, ...], top_k: int) -> None:
    """Ask one question and exit."""
    store = VectorStore()
    chat = Chat(store, k=top_k)
    q = " ".join(question)
    answer = chat.ask(q)
    _render_answer(answer)


@cli.command()
@click.option("-k", "top_k", default=5, show_default=True, help="How many chunks to retrieve.")
def chat(top_k: int) -> None:
    """Interactive chat loop. Type 'exit' to quit, 'reset' to clear history."""
    store = VectorStore()
    session = Chat(store, k=top_k)
    console.print("[bold]chat[/bold] - type 'exit' to quit, 'reset' to clear history.\n")
    while True:
        try:
            q = console.input("[bold green]> [/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not q:
            continue
        if q.lower() in {"exit", "quit"}:
            break
        if q.lower() == "reset":
            session.reset()
            console.print("[dim](history cleared)[/dim]")
            continue
        try:
            answer = session.ask(q)
        except Exception as e:
            console.print(f"[red]error:[/red] {e}")
            continue
        _render_answer(answer)


if __name__ == "__main__":
    cli()
