# C4PM

**Cursor for Product Management** — a CLI that turns customer interview transcripts into ranked problems and agent-ready product specs.

Drop a folder of interview transcripts. Get a ranked list of what to build, backed by exact user quotes. Feed the spec to Cursor or Claude Code and start building.

```
c4pm analyze interviews/
c4pm spec interviews/ -o spec.json
cursor spec.json   # or feed to any coding agent
```

---

## How It Works

```
transcripts/          c4pm analyze        c4pm spec
┌──────────┐         ┌──────────────┐    ┌──────────────┐
│ .txt/.md  │───────▶│ Extract      │───▶│ JSON spec    │───▶ Cursor / Claude Code
│ files     │        │ Rank         │    │ ready to     │     starts building
└──────────┘         │ Score (1-16) │    │ implement    │
                     └──────────────┘    └──────────────┘
```

**Three AI steps, zero manual work:**

1. **Extract** — Clusters raw feedback into 4-7 distinct problems with exact quotes and speaker attribution
2. **Rank** — Scores each problem on Reach, Intensity, User Value, and Confidence (max 16 points) using a reasoning model
3. **Spec** — Generates a structured JSON spec for the #1 problem with user stories, acceptance criteria, API design, and evidence

---

## Install

```bash
git clone https://github.com/your-org/c4pm.git
cd c4pm
pip install -e .
```

Set your OpenAI API key:

```bash
export OPENAI_API_KEY=sk-...
# or create a .env file
echo "OPENAI_API_KEY=sk-..." > .env
```

Requires Python 3.9+.

---

## Usage

### Analyze: Find and rank problems

```bash
c4pm analyze <transcript-dir> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--top`, `-n` | Number of problems to show (default: 5) |
| `--verbose`, `-v` | Show detailed extraction and ranking logs |

**Example:**

```bash
$ c4pm analyze sample_data/ -n 3

╭──────────────────────────────────────────────────────╮
│ C4PM - Analyzing customer feedback                   │
╰──────────────────────────────────────────────────────╯

Loading transcripts...
  Loaded 6 transcripts
    - Sarah Chen (Engineering Manager)
    - Marcus Johnson (Head of Product)
    - Priya Patel (Founder/CEO)
    - David Kim (Senior Product Manager)
    - Meera Krishnamurthy (Head of Product)
    - Raj Patel (Senior Product Manager)

Extracting problems...
  Found 5 distinct problems

Ranking by impact...

============================================================
PROBLEM RANKING SUMMARY

┏━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ #   ┃ Problem                      ┃ Score ┃ Severity   ┃ Confidence ┃
┡━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ 1   │ Manual, Biased Feedback      │ 15/16 │ major_pain │ high       │
│     │ Synthesis                    │       │            │            │
│ 2   │ No Evidence-Based            │ 14/16 │ major_pain │ high       │
│     │ Prioritization Framework     │       │            │            │
│ 3   │ Lack of Automated Problem    │ 13/16 │ major_pain │ high       │
│     │ Clustering                   │       │            │            │
└─────┴──────────────────────────────┴───────┴────────────┴────────────┘
```

Each problem includes:
- **Scoring breakdown** — Reach (1-5), Intensity (1-5), User Value (1-3), Confidence (1-3)
- **Evidence** — Up to 3 exact quotes with speaker name and role
- **Mentioned by** — Which interviewees raised the issue
- **Urgency signals** — Emotional language detected (e.g. "drowning", "broken", "disaster")
- **Reasoning** — Why this problem ranks where it does
- **Tradeoffs** — What happens if you don't solve it

---

### Spec: Generate a build spec

```bash
c4pm spec <transcript-dir> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--output`, `-o` | Save spec to a JSON file (default: stdout) |
| `--verbose`, `-v` | Show detailed logs |

**Example:**

```bash
$ c4pm spec sample_data/ -o spec.json
```

The generated spec is structured JSON containing:

```
problem_statement        What exactly is broken, for whom, with evidence
user_stories             5 role-specific stories with action and benefit
proposed_solution        Summary, key features, data model, API changes, workflow
acceptance_criteria      Testable conditions for done
out_of_scope             What NOT to build
success_metrics          Leading and lagging indicators
risks                    Technical, adoption, integration risks with mitigations
implementation_hints     Concrete tech stack and architecture suggestions
evidence_summary         Direct user quotes backing the spec
priority_justification   Why this problem was ranked #1
```

Feed the JSON directly to a coding agent:

```bash
# Cursor
cursor spec.json

# Claude Code
cat spec.json | claude "implement this spec"
```

---

## Transcript Format

Each interview is a `.txt` or `.md` file. Add metadata in the first few lines for better attribution:

```
Interviewee: Sarah Chen
Role: Engineering Manager
Company: Acme Corp
Date: 2024-01-15

---

Interviewer: Tell me about your current workflow...

Sarah: Honestly, it's a mess. We have user feedback
coming from everywhere...
```

Supported metadata fields: `Interviewee`, `Role`, `Company`, `Date`, `User Type`

All fields are optional. C4PM works without metadata — you just get less precise attribution.

---

## Scoring Framework

Each problem is scored across four dimensions:

| Dimension | Range | What it measures |
|-----------|-------|------------------|
| **Reach** | 1-5 | How many users are affected |
| **Intensity** | 1-5 | How painful the problem is |
| **User Value** | 1-3 | How valuable the affected users are |
| **Confidence** | 1-3 | How strong the evidence is |

**Total: /16 points.** No ties — every problem gets a unique score with head-to-head comparison.

Hard rules enforce honesty:
- If only 1 user mentioned it → Confidence = 1
- If fewer than 3 interviews → Confidence capped at 2

---

## Project Structure

```
c4pm/
  cli.py              CLI entry point (Typer + Rich)
  ingest/
    loader.py          Load .txt/.md transcripts, extract metadata
  reasoning/
    extractor.py       Cluster feedback into problems (gpt-4.1-mini)
    ranker.py          Score and rank problems (gpt-5.1-codex-mini)
  output/
    spec.py            Generate structured JSON spec (gpt-4.1-mini)
```

---

## Requirements

- Python 3.9+
- OpenAI API key
- Dependencies: `typer`, `rich`, `openai`, `python-dotenv`

---

## License

MIT
