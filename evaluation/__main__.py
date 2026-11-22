# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic==2.9.2", "typer==0.29.2", "PyMuPDF==1.24.10"]
# ///
# How to run: .venv/Scripts/python.exe -m evaluation --help
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Annotated, Callable

import typer
from pydantic import ValidationError

from evaluation.artifacts import Provenance, ensure_new_output, provenance, write_report
from evaluation.benchmark import BenchmarkOptions, benchmark
from evaluation.inventory import inventory
from evaluation.metrics import Score, score
from evaluation.models import EvaluationError, FrozenModel, Split, load_queries, load_rankings

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False, add_completion=False,
                  help="F00 local inventory, offline scoring and isolated function benchmarks.")


class ScoreArtifact(FrozenModel):
    kind: str = "score"
    provenance: Provenance
    corpus_id: str
    query_set_sha256: str
    results_sha256: str
    split: Split
    score: Score


def _run(action: Callable[[], None]) -> None:
    try:
        action()
    except EvaluationError as error:
        typer.echo(f"ERROR {error.code}", err=True)
        raise typer.Exit(2) from None
    except (OSError, sqlite3.Error, ValidationError, UnicodeError) as error:
        typer.echo(f"ERROR {type(error).__name__}", err=True)
        raise typer.Exit(2) from None


@app.command("inventory")
def inventory_command(
    root: Annotated[Path, typer.Option(help="Explicit corpus directory; no dotenv lookup.")],
    output: Annotated[Path, typer.Option(help="New report file; existing paths are rejected.")],
    database: Annotated[Path | None, typer.Option(help="Optional explicit database source, opened read only.")] = None,
) -> None:
    def execute() -> None:
        ensure_new_output(output)
        write_report(inventory(root, database), output)
        typer.echo("inventory report written")
    _run(execute)


@app.command("score")
def score_command(
    queries: Annotated[Path, typer.Option()],
    results: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    split: Annotated[Split, typer.Option()] = "dev",
    k: Annotated[int, typer.Option(min=1)] = 5,
) -> None:
    def execute() -> None:
        ensure_new_output(output)
        dataset = load_queries(queries)
        rankings = load_rankings(results, dataset, split)
        report = ScoreArtifact(provenance=provenance(), corpus_id=dataset.corpus_id,
            query_set_sha256=dataset.sha256, results_sha256=rankings.sha256, split=split,
            score=score(dataset.selected(split), rankings.rankings, k))
        write_report(report, output)
        typer.echo("score report written")
    _run(execute)


@app.command("benchmark")
def benchmark_command(
    database: Annotated[Path, typer.Option()],
    queries: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    split: Annotated[Split, typer.Option()] = "dev",
    k: Annotated[int, typer.Option(min=1)] = 5,
    warmup: Annotated[int, typer.Option(min=0)] = 5,
    repeats: Annotated[int, typer.Option(min=1)] = 10,
    concurrency: Annotated[int, typer.Option(min=1)] = 1,
) -> None:
    def execute() -> None:
        ensure_new_output(output)
        dataset = load_queries(queries)
        options = BenchmarkOptions(split=split, k=k, warmup=warmup, repeats=repeats, concurrency=concurrency)
        write_report(benchmark(database, dataset, options), output)
        typer.echo("benchmark report written")
    _run(execute)


if __name__ == "__main__":
    app()
