"""Generate agent-consumable product specs."""

import json
from pathlib import Path
from typing import Dict, List
from openai import OpenAI
from rich.console import Console
from rich.syntax import Syntax

console = Console()

SPEC_PROMPT = """You are generating a product specification for an AI coding agent (Cursor, Claude Code, etc).

The spec must be SPECIFIC and ACTIONABLE - not generic advice that could apply to any product.

PROBLEM TO SOLVE:
{problem}

EVIDENCE FROM USER RESEARCH:
{evidence}

SCORING BREAKDOWN:
{scoring}

Generate a spec with these EXACT sections:

1. problem_statement: 2-3 sentences describing the specific problem. Reference user quotes.

2. user_stories: 3 user stories in "As [role], I want [action], so that [benefit]" format.
   - Make them SPECIFIC to the evidence above
   - Include the actual pain points users mentioned

3. proposed_solution:
   - summary: One paragraph describing the core solution
   - ui_changes: Specific UI elements to add/modify (be concrete: "Add a button labeled X in the Y panel")
   - data_model_changes: Specific fields/tables (e.g., "Add 'last_synced_at' timestamp to User table")
   - api_changes: Any new endpoints or modifications
   - workflow_changes: How the user flow changes step-by-step

4. acceptance_criteria: 5-7 testable criteria (things QA could verify)
   - Write as "Given X, When Y, Then Z" or clear pass/fail conditions

5. out_of_scope: What we're explicitly NOT building (prevents scope creep)

6. success_metrics: How we'll know this worked
   - Include baseline expectations (e.g., "Reduce time from X to Y")
   - Reference the user pain points that should be resolved

7. risks: What could go wrong technically or with adoption

8. implementation_hints: Specific technical guidance for the coding agent
   - Suggest libraries, patterns, or approaches
   - Reference existing code/systems if mentioned by users

9. evidence_summary: Key quotes that justify this spec (2-3 quotes)

Make the spec SPECIFIC enough that a developer could build it without asking clarifying questions.

Respond with valid JSON.
"""


def generate_spec(problem: Dict, transcripts: List[Dict]) -> Dict:
    """
    Generate an agent-consumable spec for the top problem.
    """
    client = OpenAI()

    # Format evidence with attribution
    evidence_list = problem.get("evidence", [])
    evidence = "\n".join([f'- "{e}"' for e in evidence_list])

    # Format scoring if available
    scoring = problem.get("scoring", {})
    scoring_str = ""
    if scoring:
        for factor, data in scoring.items():
            if isinstance(data, dict):
                scoring_str += f"- {factor}: {data.get('score', '?')}/{'3' if factor in ['reach', 'intensity'] else '2'} - {data.get('reason', '')}\n"

    prompt = SPEC_PROMPT.format(
        problem=json.dumps(problem, indent=2),
        evidence=evidence,
        scoring=scoring_str or "Not available",
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=4096,
        temperature=0.3,
        messages=[
            {"role": "system", "content": "You are a technical product manager who writes clear, specific, actionable specs. You never write generic requirements - everything is concrete and testable."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
    )

    response_text = response.choices[0].message.content

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
