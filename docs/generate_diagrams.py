#!/usr/bin/env python3
"""Generate PNG images from Mermaid diagrams in docs/diagrams.md.

Requires mermaid-cli (mmdc) installed globally:
    npm install -g @mermaid-js/mermaid-cli

Usage:
    python docs/generate_diagrams.py

Output:
    docs/images/*.png — one PNG per diagram
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

DOCS_DIR = Path(__file__).parent
DIAGRAMS_FILE = DOCS_DIR / "diagrams.md"
IMAGES_DIR = DOCS_DIR / "images"

MERMAID_BLOCK_RE = re.compile(
    r"## \d+\.\s+(.+?)\n.*?```mermaid\n(.*?)```",
    re.DOTALL,
)


def slugify(name: str) -> str:
    """Convert a diagram title to a filename-safe slug."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def main() -> None:
    if not DIAGRAMS_FILE.exists():
        print(f"ERROR: {DIAGRAMS_FILE} not found")
        sys.exit(1)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    content = DIAGRAMS_FILE.read_text(encoding="utf-8")
    diagrams = MERMAID_BLOCK_RE.findall(content)

    if not diagrams:
        print("No Mermaid diagrams found in diagrams.md")
        sys.exit(1)

    print(f"Found {len(diagrams)} diagrams to render")

    for title, mermaid_src in diagrams:
        slug = slugify(title)
        out_path = IMAGES_DIR / f"{slug}.png"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False, encoding="utf-8") as tmp:
            tmp.write(mermaid_src.strip())
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                ["mmdc", "-i", tmp_path, "-o", str(out_path), "-b", "transparent"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                print(f"  ✅ {title} → {out_path.name}")
            else:
                print(f"  ❌ {title} — mmdc error: {result.stderr[:200]}")
        except FileNotFoundError:
            print("  ❌ mmdc not found. Install with: npm install -g @mermaid-js/mermaid-cli")
            sys.exit(1)
        except subprocess.TimeoutExpired:
            print(f"  ❌ {title} — timed out")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    print(f"\nDone! Images saved to {IMAGES_DIR}")


if __name__ == "__main__":
    main()
