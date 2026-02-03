"""Load and parse interview transcripts."""

from pathlib import Path
from typing import List, Dict


def load_transcripts(input_dir: Path) -> List[Dict]:
    """
    Load all transcript files from a directory.

    Supports: .txt, .md files
    Each file is treated as one interview.

    Returns list of dicts with:
        - filename: source file
        - content: raw text
        - metadata: extracted metadata (if any)
    """
    transcripts = []

    for ext in ["*.txt", "*.md"]:
        for filepath in input_dir.glob(ext):
            content = filepath.read_text(encoding="utf-8")

            transcript = {
                "filename": filepath.name,
                "content": content,
                "metadata": extract_metadata(content),
            }
            transcripts.append(transcript)

    return transcripts


def extract_metadata(content: str) -> Dict:
    """
    Extract metadata from transcript content.

    Looks for common patterns:
        - "Interviewee: ..."
        - "Role: ..."
        - "Company: ..."
        - "Date: ..."
    """
    metadata = {}
    lines = content.split("\n")[:20]  # Check first 20 lines

    patterns = {
        "interviewee": ["interviewee:", "name:", "participant:"],
        "role": ["role:", "title:", "position:"],
        "company": ["company:", "organization:", "org:"],
        "date": ["date:", "interview date:"],
        "user_type": ["user type:", "segment:", "type:"],
    }

    for line in lines:
        line_lower = line.lower().strip()
        for field, prefixes in patterns.items():
            for prefix in prefixes:
                if line_lower.startswith(prefix):
                    value = line[len(prefix):].strip().strip(":").strip()
                    metadata[field] = value
                    break

    return metadata
