"""Extract problems from customer feedback using LLM reasoning."""

import json
import os
import time
from typing import List, Dict
from openai import OpenAI
from rich.console import Console

console = Console()

EXTRACT_PROMPT = """You are analyzing customer interview transcripts to identify the core product problems.

CRITICAL RULES:
1. Extract 4-7 DISTINCT problems maximum. AGGRESSIVELY cluster related issues.
   - If two problems share the same root cause, MERGE them into one.
   - "No synthesis tools" and "Manual feedback processing" are the SAME problem. Merge them.
   - "No evidence for decisions" and "Can't defend priorities" are the SAME problem. Merge them.
   - Ask yourself: "Would the SAME feature solve both?" If yes, merge.
2. Evidence MUST be EXACT QUOTES copied verbatim from transcripts. No paraphrasing.
   - Format: "Speaker Name (Role): 'exact quote here'"
   - Always include speaker name and role for attribution.
3. Focus on ROOT CAUSES, not symptoms. "Users can't find X" is a symptom; "Navigation model is broken" is the root cause.
4. Only include problems mentioned by 2+ users OR with strong emotional language (frustration, "huge pain", "broken", "terrified", etc.)

For each problem:
- name: Clear, specific name (3-6 words) describing the ROOT CAUSE
- description: What's broken and why it matters (2-3 sentences). Be specific to this domain.
- evidence: Array of 2-4 EXACT quotes with speaker attribution: "Speaker (Role): 'quote'"
- mentioned_by: Array of objects listing WHO mentioned this: [{{"name": "...", "role": "..."}}]
- user_segment: Who is affected ("founders", "PMs at growth companies", "engineering managers", etc.)
- severity: "blocker" (can't do their job) | "major_pain" (significant friction) | "annoyance" (nice to fix)
- frequency: How many of the {num_transcripts} transcripts mention this?
- urgency_signals: Array of strong emotional words/phrases from transcripts that indicate urgency (e.g., "soul-crushing", "terrified", "broken", "threatens to leave")
- conflicts: If users DISAGREE about this problem or want opposite solutions, describe the conflict. Otherwise null.

TRANSCRIPTS:
{transcripts}

Respond with a JSON object:
{{
  "problems": [
    {{
      "name": "...",
      "description": "...",
      "evidence": ["Speaker (Role): 'exact quote'", "Speaker2 (Role): 'exact quote'"],
      "mentioned_by": [{{"name": "Speaker", "role": "Role"}}, {{"name": "Speaker2", "role": "Role"}}],
      "user_segment": "...",
      "severity": "blocker|major_pain|annoyance",
      "frequency": N,
      "urgency_signals": ["word or phrase 1", "word or phrase 2"],
      "conflicts": null
    }}
  ],
  "synthesis_notes": "Brief explanation of how you clustered these problems. Explain any merges you made."
}}

QUALITY CHECK before responding:
- Are any two problems really the same root cause? If yes, MERGE.
- Does every quote include "Speaker (Role): 'quote'"? If not, FIX.
- Is frequency accurate? Count carefully.
- Would a PM reading this know EXACTLY what's broken and WHO is affected?
"""


def extract_problems(transcripts: List[Dict], verbose: bool = False) -> List[Dict]:
    """
    Extract problems from transcripts using GPT.

    Returns list of problem dicts with:
        - name, description, evidence, user_segment, severity, frequency
    """
    client = OpenAI()

    # Combine transcripts into single context with clear markers
    combined = "\n\n" + "="*50 + "\n\n".join([
        f"[INTERVIEW: {t['filename']}]\n[Interviewee: {t['metadata'].get('interviewee', 'Unknown')}]\n[Role: {t['metadata'].get('role', 'Unknown')}]\n\n{t['content']}"
        for t in transcripts
    ])

    # Truncate if too long (keep under ~120k chars for GPT-4)
    if len(combined) > 120000:
        combined = combined[:120000] + "\n\n[TRUNCATED]"

    prompt = EXTRACT_PROMPT.format(
        transcripts=combined,
        num_transcripts=len(transcripts)
    )

    if verbose:
        console.print("[dim]Calling GPT for problem extraction...[/dim]")

    # Retry with backoff for rate limits
    for attempt in range(3):
        try:
            response = client.responses.create(
                model="gpt-4.1-mini-2025-04-14",
                instructions="You are a product analyst expert at synthesizing user research into actionable insights. You never paraphrase - you always use exact quotes.",
                input=prompt,
                text={"format": {"type": "json_object"}},
                max_output_tokens=4096,
                temperature=0.3,
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
        if isinstance(parsed, dict) and "problems" in parsed:
            problems = parsed["problems"]
            if verbose and "synthesis_notes" in parsed:
                console.print(f"[dim]Synthesis: {parsed['synthesis_notes']}[/dim]")
        elif isinstance(parsed, list):
            problems = parsed
        else:
            problems = list(parsed.values())[0] if parsed else []
    except json.JSONDecodeError as e:
        console.print(f"[red]Failed to parse response: {e}[/red]")
        if verbose:
            console.print(f"[dim]Raw response: {response_text[:500]}[/dim]")
        problems = []

    return problems
