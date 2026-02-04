#!/usr/bin/env python3
"""C4PM - Cursor for Product Management CLI"""

import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
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
    top: int = typer.Option(5, "--top", "-n", help="Number of top problems to show"),
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

    # Show interviewee names
    for t in transcripts:
        name = t['metadata'].get('interviewee', t['filename'])
        role = t['metadata'].get('role', '')
        console.print(f"    - {name} ({role})" if role else f"    - {name}")

    # Data quality warning
    if len(transcripts) < 3:
        console.print(f"\n  [yellow]Warning: Small sample size ({len(transcripts)} interviews). Confidence levels may be limited.[/yellow]")

    # Step 2: Extract problems
    console.print("\n[bold]Extracting problems...[/bold]")
    problems = extract_problems(transcripts, verbose=verbose)
    console.print(f"  Found {len(problems)} distinct problems")

    # Step 3: Rank problems
    console.print("\n[bold]Ranking by impact...[/bold]")
    ranked = rank_problems(problems, transcripts, verbose=verbose)

    # Summary table
    max_score = 16
    console.print("\n" + "="*60)
    console.print("[bold green]PROBLEM RANKING SUMMARY[/bold green]\n")

    summary_table = Table(show_header=True, header_style="bold")
    summary_table.add_column("#", style="cyan", width=3)
    summary_table.add_column("Problem", style="white", min_width=25)
    summary_table.add_column("Score", style="bold", width=7)
    summary_table.add_column("Severity", width=12)
    summary_table.add_column("Confidence", width=12)

    for i, problem in enumerate(ranked[:top], 1):
        score = problem.get('impact_score', '?')
        severity = problem.get('severity', '?')
        conf = problem.get('confidence', '?')
        sev_style = "red" if severity == "blocker" else "yellow" if severity == "major_pain" else "dim"
        summary_table.add_row(
            str(i),
            problem.get('name', '?'),
            f"{score}/{max_score}",
            f"[{sev_style}]{severity}[/{sev_style}]",
            conf
        )

    console.print(summary_table)

    # Detailed output
    console.print("\n" + "="*60)
    console.print("[bold green]DETAILED ANALYSIS[/bold green]\n")

    for i, problem in enumerate(ranked[:top], 1):
        console.print(f"[bold cyan]{i}. {problem['name']}[/bold cyan]")
        console.print(f"   [bold]Impact Score: {problem.get('impact_score', 'N/A')}/{max_score}[/bold]")

        # Show scoring breakdown if available
        if "scoring" in problem:
            scoring = problem["scoring"]
            console.print(f"   Scoring breakdown:")
            for factor, max_val in [("reach", 5), ("intensity", 5), ("user_value", 3), ("confidence", 3)]:
                if factor in scoring:
                    s = scoring[factor]
                    console.print(f"     {factor.replace('_', ' ').title()}: {s.get('score', '?')}/{max_val} - {s.get('reason', '')[:75]}")

        console.print(f"\n   [dim]Affected:[/dim] {problem.get('user_segment', 'Unknown')}")
        console.print(f"   [dim]Severity:[/dim] {problem.get('severity', 'Unknown')}")

        # Show who mentioned it
        mentioned_by = problem.get("mentioned_by", [])
        if mentioned_by:
            names = [f"{m.get('name', '?')} ({m.get('role', '?')})" for m in mentioned_by]
            console.print(f"   [dim]Mentioned by:[/dim] {', '.join(names)}")

        # Show urgency signals
        urgency = problem.get("urgency_signals", [])
        if urgency:
            console.print(f"   [red]Urgency signals:[/red] {', '.join(urgency[:4])}")

        # Show evidence quotes (longer, up to 3)
        evidence = problem.get("evidence", [])
        if evidence:
            console.print(f"\n   [yellow]Evidence:[/yellow]")
            for quote in evidence[:3]:
                console.print(f"   \"{quote[:200]}{'...' if len(quote) > 200 else ''}\"")

        console.print(f"\n   [green]Reasoning:[/green] {problem.get('reasoning', 'N/A')}")

        if "tradeoffs" in problem:
            console.print(f"   [red]If ignored:[/red] {problem['tradeoffs']}")

        # Show conflicts if any
        conflicts = problem.get("conflicts")
        if conflicts:
            console.print(f"   [magenta]Conflict:[/magenta] {conflicts}")

        console.print("\n" + "-"*60 + "\n")

    # Footer
    console.print(f"[dim]Analyzed {len(transcripts)} interviews | Extracted {len(problems)} problems | Showing top {min(top, len(ranked))}[/dim]")
    console.print(f"[dim]Run 'c4pm spec {input_dir}' to generate a build spec for the #1 problem[/dim]")


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
    top_problem = ranked[0]
    console.print(f"\n[bold]Generating build spec for: {top_problem.get('name', 'top problem')}[/bold]")
    console.print(f"[dim]Impact score: {top_problem.get('impact_score', '?')}/16 | Severity: {top_problem.get('severity', '?')}[/dim]")
    spec_data = generate_spec(top_problem, transcripts)

    # Output
    if output:
        output_json(spec_data, output)
        console.print(f"\n[green]Spec written to {output}[/green]")
    else:
        output_json(spec_data)

    console.print("\n[dim]This spec can be fed directly to Cursor or Claude Code[/dim]")


if __name__ == "__main__":
    app()
