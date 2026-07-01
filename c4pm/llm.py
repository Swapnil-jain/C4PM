"""Shared OpenAI client helpers: key handling, retry-with-backoff, and JSON parsing.

All three AI modules (extractor, ranker, spec) route their OpenAI calls through
``call_with_retry`` so the retry/backoff logic lives in exactly one place.
"""

import json
import os
import time
from typing import Any, Optional

from openai import OpenAI
from rich.console import Console

console = Console()

_client: Optional[OpenAI] = None


def has_api_key() -> bool:
    """Return True if an OpenAI API key is available in the environment."""
    return bool(os.environ.get("OPENAI_API_KEY"))


def get_client() -> OpenAI:
    """Return a shared OpenAI client, validating that an API key is present."""
    global _client
    if _client is None:
        if not has_api_key():
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to your environment or a .env file."
            )
        _client = OpenAI()
    return _client


def _is_rate_limit(error: Exception) -> bool:
    message = str(error).lower()
    return "rate_limit" in message or "429" in message


def call_with_retry(*, verbose: bool = False, max_attempts: int = 3, **kwargs) -> Any:
    """Call ``client.responses.create`` with exponential backoff on rate limits.

    Retries only on rate-limit (429) errors, waiting 10s, 20s, ... between
    attempts. Any other error is raised immediately. If every attempt is
    rate-limited, the last error is raised (never returns without a response).
    """
    client = get_client()
    last_error: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            return client.responses.create(**kwargs)
        except Exception as e:  # noqa: BLE001 - non-rate-limit errors re-raised below
            last_error = e
            if not _is_rate_limit(e):
                raise
            # Don't sleep after the final attempt - we're about to give up.
            if attempt < max_attempts - 1:
                wait = (attempt + 1) * 10
                if verbose:
                    console.print(f"[yellow]Rate limited, waiting {wait}s...[/yellow]")
                time.sleep(wait)

    raise last_error


def parse_json_response(response_text: str) -> Any:
    """Parse JSON from a model response, tolerating surrounding whitespace."""
    return json.loads(response_text.strip())
