"""Generate an embedding with the same model used by long-term memory.

Usage:
    uv run python scripts/generate_embedding.py "hello world"
    uv run python scripts/generate_embedding.py --raw "hello world"
    uv run python scripts/generate_embedding.py --json "hello world"
    echo "hello world" | uv run python scripts/generate_embedding.py --raw

The script uses LONG_TERM_MEMORY_EMBEDDER_* from .env.development, so the
vector matches the one mem0 writes to pgvector for the same text.
"""

import argparse
import contextlib
import io
import json
import math
import sys
from pathlib import Path

from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# The zh-CN console defaults to GBK; force UTF-8 so Chinese text renders correctly.
for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")

# config.py prints the loaded env file; keep stdout clean for --raw/--json.
with contextlib.redirect_stdout(io.StringIO()):
    from app.core.config import settings  # noqa: E402


def base_url() -> str:
    """Return the embedding endpoint used by long-term memory."""
    return (
        settings.LONG_TERM_MEMORY_EMBEDDER_BASE_URL
        or settings.OPENAI_BASE_URL
        or "https://api.openai.com/v1"
    )


def generate_embedding(text: str) -> list[float]:
    """Embed text with the configured long-term-memory embedding model."""
    client = OpenAI(
        api_key=settings.LONG_TERM_MEMORY_EMBEDDER_API_KEY,
        base_url=base_url(),
    )

    kwargs: dict = {}
    # SiliconFlow rejects the optional `dimensions` parameter; OpenAI accepts it.
    if settings.LONG_TERM_MEMORY_EMBEDDER_PROVIDER != "openai_compatible":
        kwargs["dimensions"] = settings.LONG_TERM_MEMORY_EMBEDDER_DIMS

    response = client.embeddings.create(
        input=[text],
        model=settings.LONG_TERM_MEMORY_EMBEDDER_MODEL,
        **kwargs,
    )
    return list(response.data[0].embedding)


def vector_json(vector: list[float]) -> str:
    """Render a compact JSON array, matching pgvector's text format."""
    return json.dumps(vector, separators=(",", ":"))


def read_text(parts: list[str], parser: argparse.ArgumentParser) -> str:
    """Join positional arguments or read text from stdin."""
    text = " ".join(parts).strip()
    if not text:
        text = sys.stdin.read().strip()
    if not text:
        parser.error("provide text as arguments or via stdin")
    return text


def main() -> int:
    """Parse arguments, call the embedding model, and print the vector."""
    parser = argparse.ArgumentParser(description="Generate an embedding with the project's memory embedder.")
    parser.add_argument("text", nargs="*", help="Text to embed; omit to read from stdin")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print a JSON object with metadata and vector")
    output.add_argument("--raw", action="store_true", help="Print only the vector as a JSON array")
    args = parser.parse_args()

    text = read_text(args.text, parser)

    print("Generating embedding...", file=sys.stderr)
    try:
        vector = generate_embedding(text)
    except Exception as exc:
        print(f"Embedding failed: {exc}", file=sys.stderr)
        return 1

    if not vector:
        print("Embedding model returned an empty vector.", file=sys.stderr)
        return 1

    if args.raw:
        print(vector_json(vector))
        return 0

    if args.json:
        print(
            json.dumps(
                {
                    "text": text,
                    "model": settings.LONG_TERM_MEMORY_EMBEDDER_MODEL,
                    "base_url": base_url(),
                    "dimensions": len(vector),
                    "vector": vector,
                },
                ensure_ascii=False,
            )
        )
        return 0

    preview = text.replace("\n", " ")
    if len(preview) > 200:
        preview = preview[:197] + "..."

    norm = math.sqrt(sum(value * value for value in vector))
    print(f"text:        {preview}")
    print(f"model:       {settings.LONG_TERM_MEMORY_EMBEDDER_MODEL}")
    print(f"base_url:    {base_url()}")
    print(f"dimensions:  {len(vector)}")
    print(f"min:         {min(vector):.8f}")
    print(f"max:         {max(vector):.8f}")
    print(f"mean:        {sum(vector) / len(vector):.8f}")
    print(f"l2_norm:     {norm:.8f}")
    print("\nvector (raw):")
    print(vector_json(vector))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
