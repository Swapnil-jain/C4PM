"""Generate agent-consumable product specs."""

import json
import time
from pathlib import Path
from typing import Dict, List
from openai import OpenAI
from rich.console import Console
from rich.syntax import Syntax

console = Console()

SPEC_PROMPT = """You are generating a product specification for an AI coding agent (Cursor, Claude Code, etc).

The spec must be SPECIFIC and ACTIONABLE. A developer reading this should be able to start building IMMEDIATELY.

ANTI-GENERIC RULE: Every element must reference the SPECIFIC domain and users from the research.
- BAD: "Add a dashboard" / "Improve user experience"
- GOOD: "Add a compliance-export panel that generates SOC 2-formatted audit logs" / "Reduce PM synthesis time from 5 hours to 30 minutes"

PROBLEM TO SOLVE:
{problem}

EVIDENCE FROM USER RESEARCH:
{evidence}

WHO IS AFFECTED:
{mentioned_by}

SCORING BREAKDOWN:
{scoring}

ADDITIONAL CONTEXT FROM INTERVIEWS:
{transcript_context}

Generate a spec with these EXACT sections:

1. problem_statement: 2-3 sentences describing the specific problem. Reference user quotes with speaker names.

2. user_stories: Array of objects, each with "role", "action", "benefit" fields.
   - 3-5 user stories, each tied to a SPECIFIC quote or user from the research.
   - Use actual role titles from the interviews (not generic "user").

3. proposed_solution:
   - summary: One paragraph. Must reference the specific domain/context.
   - key_features: Array of 3-5 concrete feature descriptions (what it DOES, not what it IS)
   - data_model_changes: Specific fields/tables with types (e.g., "Add 'drift_status: enum(synced, drifted, unknown)' to ServiceConfig table")
   - api_changes: Specific endpoints with methods and payloads
   - workflow_changes: Step-by-step user flow, numbered

4. acceptance_criteria: 5-7 testable criteria
   - MUST be "Given X, When Y, Then Z" format
   - Each criterion must be verifiable by QA without ambiguity

5. out_of_scope: What we're explicitly NOT building (prevents scope creep)

6. success_metrics: Measurable outcomes tied to user pain points
   - Reference specific numbers from interviews (e.g., "Reduce from 5 hours to 1 hour" if a user said they spend 5 hours)
   - Include both leading indicators (adoption) and lagging indicators (retention/satisfaction)

7. risks: Technical and adoption risks with mitigation strategies

8. implementation_hints: Specific technical guidance
   - Suggest concrete libraries/frameworks with versions
   - Describe data flow and architecture patterns
   - Note any integration points

9. evidence_summary: 3-5 key quotes with full speaker attribution: "Name (Role): 'quote'"

10. priority_justification: Why this problem was ranked #1 - reference the scoring breakdown

Respond with valid JSON. Every string value must be specific to this domain - no generic placeholders.
"""


def generate_spec(problem: Dict, transcripts: List[Dict]) -> Dict:
    """
    Generate an agent-consumable spec for the top problem.
    """
    client = OpenAI()

    # Format evidence with attribution
    evidence_list = problem.get("evidence", [])
    evidence = "\n".join([f'- "{e}"' for e in evidence_list])

    # Format mentioned_by
    mentioned_by = problem.get("mentioned_by", [])
    mentioned_str = "\n".join([f"- {m.get('name', '?')} ({m.get('role', '?')})" for m in mentioned_by]) if mentioned_by else "Not available"

    # Format scoring if available
    scoring = problem.get("scoring", {})
    scoring_str = ""
    if scoring:
        for factor, data in scoring.items():
            if isinstance(data, dict):
                max_val = 5 if factor in ['reach', 'intensity'] else 3
                scoring_str += f"- {factor}: {data.get('score', '?')}/{max_val} - {data.get('reason', '')}\n"

    # Include relevant transcript excerpts for richer context
    transcript_context = "\n\n".join([
        f"[{t['metadata'].get('interviewee', 'Unknown')} ({t['metadata'].get('role', 'Unknown')})]\n{t['content'][:2000]}"
        for t in transcripts[:6]
    ])

    prompt = SPEC_PROMPT.format(
        problem=json.dumps(problem, indent=2),
        evidence=evidence,
        mentioned_by=mentioned_str,
        scoring=scoring_str or "Not available",
        transcript_context=transcript_context,
    )

    # Retry with backoff for rate limits
    for attempt in range(3):
        try:
            response = client.responses.create(
                model="gpt-4.1-mini-2025-04-14",
                instructions="You are a technical product manager who writes clear, specific, actionable specs. You never write generic requirements - everything is concrete and testable.",
                input=prompt,
                text={"format": {"type": "json_object"}},
                max_output_tokens=6000,
                temperature=0.3,
            )
            break
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait = (attempt + 1) * 10
                console.print(f"[yellow]Rate limited, waiting {wait}s...[/yellow]")
                time.sleep(wait)
            else:
                raise

    response_text = response.output_text

    try:
        spec = json.loads(response_text.strip())
    except json.JSONDecodeError:
        spec = {
            "problem_statement": problem.get("description", ""),
            "user_stories": [],
            "proposed_solution": {
                "summary": "Unable to generate solution",
                "ui_changes": [],
                "data_model_changes": [],
                "api_changes": [],
                "workflow_changes": [],
            },
            "acceptance_criteria": [],
            "out_of_scope": [],
            "success_metrics": [],
            "risks": [],
            "implementation_hints": [],
            "evidence_summary": evidence_list[:3],
        }

    # Add metadata
    spec["_metadata"] = {
        "source_problem": problem.get("name", ""),
        "impact_score": problem.get("impact_score", 0),
        "confidence": problem.get("confidence", "unknown"),
        "user_segment": problem.get("user_segment", "unknown"),
        "severity": problem.get("severity", "unknown"),
        "generated_by": "c4pm",
        "version": "0.1.0",
    }

    # Ensure evidence is preserved
    if "evidence_summary" not in spec:
        spec["evidence_summary"] = evidence_list[:3]

    return spec


def output_json(spec: Dict, output_path: Path = None):
    """Output spec as formatted JSON."""
    json_str = json.dumps(spec, indent=2)

    if output_path:
        output_path.write_text(json_str)
    else:
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
        console.print(syntax)
