#!/usr/bin/env python3
"""C4PM - Cursor for Product Management CLI"""

import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv

# Load .env from current directory or parent
load_dotenv()
load_dotenv(Path(__file__).parent.parent / ".env")

from c4pm.ingest.loader import load_transcripts
from c4pm.reasoning.extractor import extract_problems
from c4pm.reasoning.ranker import rank_problems
from c4pm.output.spec import generate_spec, output_json

app = typer.Typer(
    name="c4pm",
    help="Turn customer feedback into executable product decisions",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    input_dir: Path = typer.Argument(..., help="Directory containing interview transcripts"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Extract and rank problems from customer feedback."""

    if not input_dir.exists():
        console.print(f"[red]Error:[/red] Directory {input_dir} does not exist")
        raise typer.Exit(1)

    console.print(Panel("C4PM - Analyzing customer feedback", style="blue"))

    # Step 1: Load transcripts
    console.print("\n[bold]Loading transcripts...[/bold]")
    transcripts = load_transcripts(input_dir)
    console.print(f"  Loaded {len(transcripts)} transcripts")

    # Data quality warning
    if len(transcripts) < 3:
        console.print(f"  [yellow]⚠ Small sample size ({len(transcripts)} interviews). Confidence levels may be limited.[/yellow]")

    # Step 2: Extract problems
    console.print("\n[bold]Extracting problems...[/bold]")
    problems = extract_problems(transcripts, verbose=verbose)
    console.print(f"  Found {len(problems)} distinct problems")

    # Step 3: Rank problems
    console.print("\n[bold]Ranking by impact...[/bold]")
    ranked = rank_problems(problems, transcripts, verbose=verbose)

    # Output results
    console.print("\n" + "="*60)
    console.print("[bold green]TOP PROBLEMS TO SOLVE[/bold green]\n")

    for i, problem in enumerate(ranked[:5], 1):
        console.print(f"[bold cyan]{i}. {problem['name']}[/bold cyan]")
        console.print(f"   [bold]Impact Score: {problem.get('impact_score', 'N/A')}/10[/bold]")

        # Show scoring breakdown if available
        if "scoring" in problem:
            scoring = problem["scoring"]
            console.print(f"   Scoring breakdown:")
            for factor in ["reach", "intensity", "user_value", "confidence"]:
                if factor in scoring:
                    s = scoring[factor]
                    console.print(f"     • {factor.title()}: {s.get('score', '?')} - {s.get('reason', '')[:60]}")

        console.print(f"\n   [dim]Affected:[/dim] {problem.get('user_segment', 'Unknown')}")
        console.print(f"   [dim]Severity:[/dim] {problem.get('severity', 'Unknown')}")

        # Show evidence quotes
        evidence = problem.get("evidence", [])
        if evidence:
            console.print(f"\n   [yellow]Evidence:[/yellow]")
            for quote in evidence[:2]:
                console.print(f"   \"{quote[:120]}{'...' if len(quote) > 120 else ''}\"")

        console.print(f"\n   [green]Reasoning:[/green] {problem.get('reasoning', 'N/A')}")

        if "tradeoffs" in problem:
            console.print(f"   [red]If ignored:[/red] {problem['tradeoffs']}")

        console.print("\n" + "-"*60 + "\n")


@app.command()
def spec(
    input_dir: Path = typer.Argument(..., help="Directory containing interview transcripts"),
    output: Path = typer.Option(None, "--output", "-o", help="Output JSON file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Generate agent-consumable product spec from feedback."""

    if not input_dir.exists():
        console.print(f"[red]Error:[/red] Directory {input_dir} does not exist")
        raise typer.Exit(1)

    console.print(Panel("C4PM - Generating Product Spec", style="blue"))

    # Load and analyze
    transcripts = load_transcripts(input_dir)
    problems = extract_problems(transcripts, verbose=verbose)
    ranked = rank_problems(problems, transcripts, verbose=verbose)

    # Generate spec for top problem
    console.print("\n[bold]Generating build spec for top problem...[/bold]")
    spec_data = generate_spec(ranked[0], transcripts)

    # Output
    if output:
        output_json(spec_data, output)
        console.print(f"\n[green]Spec written to {output}[/green]")
    else:
        output_json(spec_data)

    console.print("\n[dim]This spec can be fed directly to Cursor or Claude Code[/dim]")


if __name__ == "__main__":
    app()
