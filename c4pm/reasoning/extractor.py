"""Extract problems from customer feedback using LLM reasoning."""

import json
import os
from typing import List, Dict
from openai import OpenAI
from rich.console import Console

console = Console()

EXTRACT_PROMPT = """You are analyzing customer interview transcripts to identify the core product problems.

CRITICAL RULES:
1. Extract 5-8 DISTINCT problems maximum. Cluster similar issues together.
2. Evidence MUST be EXACT QUOTES copied verbatim from transcripts. No paraphrasing.
3. Focus on ROOT CAUSES, not symptoms. "Users can't find X" is a symptom; "Navigation is confusing" is closer to root cause.
4. Only include problems mentioned by 2+ users OR with strong emotional language (frustration, "huge pain", "broken", etc.)

For each problem:
- name: Clear, specific name (3-6 words) describing the problem itself
- description: What's broken and why it matters (2-3 sentences)
- evidence: Array of 2-4 EXACT quotes from transcripts (copy-paste, include speaker if known)
- user_segment: Who is affected ("founders", "PMs at growth companies", "engineering managers", etc.)
- severity: "blocker" (can't do their job) | "major_pain" (significant friction) | "annoyance" (nice to fix)
- frequency: How many of the {num_transcripts} transcripts mention this?

TRANSCRIPTS:
{transcripts}

Respond with a JSON object:
{{
  "problems": [
    {{
      "name": "...",
      "description": "...",
      "evidence": ["exact quote 1", "exact quote 2"],
      "user_segment": "...",
      "severity": "blocker|major_pain|annoyance",
      "frequency": N
    }}
  ],
  "synthesis_notes": "Brief explanation of how you clustered/prioritized these problems"
}}

Remember: EXACT QUOTES ONLY. Do not paraphrase or summarize user statements.
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

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=4096,
        temperature=0.3,  # Lower temperature for more consistent extraction
        messages=[
            {"role": "system", "content": "You are a product analyst expert at synthesizing user research into actionable insights. You never paraphrase - you always use exact quotes."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
    )

    response_text = response.choices[0].message.content

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
