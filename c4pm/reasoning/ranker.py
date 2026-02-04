"""Rank problems by impact using LLM reasoning."""

import json
import time
from typing import List, Dict
from openai import OpenAI
from rich.console import Console

console = Console()

RANK_PROMPT = """You are a senior product strategist helping a team decide what to build next.

DATA CONTEXT:
- Total interviews analyzed: {num_interviews}
- Be honest about confidence levels. Small samples = lower confidence.

PROBLEMS IDENTIFIED:
{problems}

ORIGINAL INTERVIEW CONTEXT:
{transcripts_summary}

YOUR TASK: Create a STRICT RANKING - which problem should be solved FIRST, SECOND, etc.

SCORING FRAMEWORK (be explicit about each factor):

1. REACH (1-5 points)
   - 1: Only 1 user mentioned it, niche use case
   - 2: 1-2 users, but represents a broader segment
   - 3: Multiple users across different roles/segments
   - 4: Most interviewees mentioned or implied it
   - 5: Universal - every interviewee is affected

2. INTENSITY (1-5 points)
   - 1: Minor annoyance, easy workaround
   - 2: Noticeable friction, workaround exists but is inconvenient
   - 3: Significant pain, workarounds are time-consuming
   - 4: Severe pain, users express strong emotion (e.g., "frustrated", "broken")
   - 5: Blocker/existential - can't do their job, threatening to leave/churn

3. USER VALUE (1-3 points)
   - 1: Affects free/trial/low-spend users
   - 2: Affects paying users or important segments
   - 3: Affects highest-value users (enterprise, champions, revenue drivers)

4. CONFIDENCE (1-3 points) - BE HONEST
   - 1: Single mention, indirect signal, OR total interviews < 3
   - 2: 2+ users mentioned it with moderate clarity
   - 3: 3+ users mentioned it with strong emotional language AND specific examples

   HARD RULE: If frequency=1, confidence MUST be 1. No exceptions.
   HARD RULE: If total interviews < 3, confidence CANNOT exceed 2.

Total possible: 16 points

ANTI-TIE RULES:
- Every problem MUST have a DIFFERENT impact_score. NO TIES.
- If two problems would tie, compare them HEAD-TO-HEAD:
  "Problem A vs B: A is more critical because [specific reason with quote]"
- Force a strict ordering: 1st, 2nd, 3rd, etc.

For EACH problem, provide:
{{
  "name": "...",
  "description": "...",
  "evidence": [...],
  "mentioned_by": [{{"name": "...", "role": "..."}}],
  "user_segment": "...",
  "severity": "...",
  "frequency": N,
  "urgency_signals": [...],
  "scoring": {{
    "reach": {{ "score": N, "reason": "..." }},
    "intensity": {{ "score": N, "reason": "..." }},
    "user_value": {{ "score": N, "reason": "..." }},
    "confidence": {{ "score": N, "reason": "..." }}
  }},
  "impact_score": N,
  "rank": N,
  "reasoning": "2-3 sentences citing SPECIFIC quotes with speaker names: 'Sarah (Eng Manager) said X, which shows...'",
  "tradeoffs": "What happens if you DON'T solve this - be concrete"
}}

CRITICAL:
- Cite specific quotes WITH speaker names in reasoning.
- NO TIES in impact_score. Force differentiation.
- Preserve the mentioned_by and urgency_signals from the extracted problems.

Respond with JSON object:
{{
  "ranked_problems": [...],
  "recommendation": "1-2 sentence executive summary of what to build first and why",
  "head_to_head": "Explain why #1 beats #2, and why #2 beats #3"
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

    # Include full transcript context for ranking (up to 4000 chars each)
    transcripts_summary = "\n\n".join([
        f"[{t['filename']} - {t['metadata'].get('interviewee', 'Unknown')} ({t['metadata'].get('role', 'Unknown')})]\n{t['content'][:4000]}"
        for t in transcripts[:12]
    ])

    prompt = RANK_PROMPT.format(
        problems=json.dumps(problems, indent=2),
        transcripts_summary=transcripts_summary,
        num_interviews=len(transcripts),
    )

    if verbose:
        console.print("[dim]Calling GPT for ranking...[/dim]")

    # Retry with backoff for rate limits
    # Using reasoning model for ranking - better at comparative judgment
    for attempt in range(3):
        try:
            response = client.responses.create(
                model="gpt-5.1-codex-mini",
                instructions="You are a product strategist who makes evidence-based recommendations. You always cite specific user quotes to justify your reasoning.",
                input=prompt,
                text={"format": {"type": "json_object"}},
                max_output_tokens=10000,
                reasoning={"effort": "medium"},
            )
            break
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait = (attempt + 1) * 10
                if verbose:
                    console.print(f"[yellow]Rate limited, waiting {wait}s...[/yellow]")
                time.sleep(wait)
            else:
                raise

    response_text = response.output_text

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
