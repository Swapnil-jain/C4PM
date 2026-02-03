"""Rank problems by impact using LLM reasoning."""

import json
from typing import List, Dict
from openai import OpenAI
from rich.console import Console

console = Console()

RANK_PROMPT = """You are a senior product strategist helping a team decide what to build next.

DATA CONTEXT:
- Total interviews analyzed: {num_interviews}
- Note: Be honest about confidence levels based on sample size

PROBLEMS IDENTIFIED:
{problems}

ORIGINAL INTERVIEW CONTEXT:
{transcripts_summary}

YOUR TASK: Rank these problems by which one the team should solve FIRST.

SCORING FRAMEWORK (be explicit about each factor):

1. REACH (1-3 points)
   - 1: Affects small subset of users
   - 2: Affects significant portion
   - 3: Affects most/all users

2. INTENSITY (1-3 points)
   - 1: Annoyance, workaround exists
   - 2: Significant friction, painful but manageable
   - 3: Blocker, can't do their job without this

3. USER VALUE (1-2 points)
   - 1: Affects lower-value users (free, small, churning)
   - 2: Affects high-value users (paying, enterprise, champions)

4. CONFIDENCE (1-2 points) - BE HONEST ABOUT DATA QUALITY
   - 1: Mentioned by only 1 user, OR indirect signals, OR small sample size
   - 2: Mentioned by 2+ users with clear quotes AND strong emotional language

   IMPORTANT: If frequency=1, confidence MUST be 1. Don't inflate confidence.

Total possible: 10 points

For EACH problem, provide:
{{
  "name": "...",
  "description": "...",
  "evidence": [...],
  "user_segment": "...",
  "severity": "...",
  "frequency": N,
  "scoring": {{
    "reach": {{ "score": N, "reason": "..." }},
    "intensity": {{ "score": N, "reason": "..." }},
    "user_value": {{ "score": N, "reason": "..." }},
    "confidence": {{ "score": N, "reason": "..." }}
  }},
  "impact_score": N,
  "reasoning": "2-3 sentence synthesis explaining why this ranking makes sense, citing specific quotes",
  "tradeoffs": "What you'd be giving up by NOT solving this problem"
}}

CRITICAL: Your reasoning must cite specific user quotes. Don't just say "users want X" - say "Sarah said 'quote here' which shows..."

Respond with JSON object:
{{
  "ranked_problems": [...],
  "recommendation": "1-2 sentence executive summary of what to build first and why"
}}

Order by impact_score descending.
"""


def rank_problems(
    problems: List[Dict],
    transcripts: List[Dict],
    verbose: bool = False
) -> List[Dict]:
    """
    Rank problems by impact using GPT.

    Returns problems with added:
        - impact_score (1-10)
        - reasoning (why this score)
        - scoring breakdown
    """
    client = OpenAI()

    # Include fuller transcript context for ranking
    transcripts_summary = "\n\n".join([
        f"[{t['filename']} - {t['metadata'].get('role', 'Unknown')}]\n{t['content'][:1500]}..."
        for t in transcripts[:10]
    ])

    prompt = RANK_PROMPT.format(
        problems=json.dumps(problems, indent=2),
        transcripts_summary=transcripts_summary,
        num_interviews=len(transcripts),
    )

    if verbose:
        console.print("[dim]Calling GPT for ranking...[/dim]")

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=4096,
        temperature=0.2,  # Very low for consistent ranking
        messages=[
            {"role": "system", "content": "You are a product strategist who makes evidence-based recommendations. You always cite specific user quotes to justify your reasoning."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
    )

    response_text = response.choices[0].message.content

    try:
        parsed = json.loads(response_text.strip())
        if isinstance(parsed, dict) and "ranked_problems" in parsed:
            ranked = parsed["ranked_problems"]
            if verbose and "recommendation" in parsed:
                console.print(f"\n[bold]Recommendation:[/bold] {parsed['recommendation']}")
        elif isinstance(parsed, list):
            ranked = parsed
        else:
            ranked = list(parsed.values())[0] if parsed else []

        # Sort by impact score descending
        ranked.sort(key=lambda x: x.get("impact_score", 0), reverse=True)

        # Add confidence field for backward compatibility
        for p in ranked:
            if "scoring" in p:
                conf_score = p["scoring"].get("confidence", {}).get("score", 1)
                p["confidence"] = "high" if conf_score >= 2 else "medium"
            else:
                p["confidence"] = "medium"

    except json.JSONDecodeError as e:
        console.print(f"[red]Failed to parse ranking response: {e}[/red]")
        ranked = [
            {**p, "impact_score": 5, "reasoning": "Unable to rank", "confidence": "low"}
            for p in problems
        ]

    return ranked
