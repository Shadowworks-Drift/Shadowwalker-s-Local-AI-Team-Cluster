"""
Agent Mesh — Code Block Extractor
──────────────────────────────────
Parses the Coder's output for code blocks and writes them to the sandbox.
No tool calling required — the Coder just writes code naturally,
and we extract it into real files.

Supports two labeling patterns:
  1. ### filename.py  or  ## filename.py  (markdown header before code block)
  2. # file: filename.py  (comment as first line inside code block)

If only one code block exists with no label, it gets saved as main.py.
"""

import re
from pathlib import Path
from typing import Optional
from tools.file_tools import write_file, create_directory

# ── Extraction Patterns ──────────────────────────────────────────────────────

# Matches: ### `filename.py`  or  ### filename.py  or  ## path/to/file.py
HEADER_PATTERN = re.compile(
    r'#{2,4}\s+`?([a-zA-Z0-9_/\\.-]+\.[a-z]+)`?\s*\n'
    r'```(?:python|py)?\s*\n'
    r'(.*?)'
    r'\n```',
    re.DOTALL
)

# Matches code blocks with # file: filename.py as first line
FILE_COMMENT_PATTERN = re.compile(
    r'```(?:python|py)?\s*\n'
    r'#\s*file:\s*([a-zA-Z0-9_/\\.-]+\.[a-z]+)\s*\n'
    r'(.*?)'
    r'\n```',
    re.DOTALL
)

# Matches any fenced code block (fallback)
GENERIC_BLOCK_PATTERN = re.compile(
    r'```(?:python|py)?\s*\n'
    r'(.*?)'
    r'\n```',
    re.DOTALL
)


def extract_code_blocks(text: str) -> list[dict]:
    """
    Extract labeled code blocks from agent output.

    Returns list of {"filename": str, "content": str} dicts.
    """
    blocks = []
    seen_spans = set()

    def _add(filename: str, content: str, start: int, end: int):
        """Add block if we haven't already captured this span."""
        span_key = (start, end)
        if span_key not in seen_spans:
            seen_spans.add(span_key)
            blocks.append({
                "filename": filename.strip().strip('`'),
                "content": content.strip(),
            })

    # Pass 1: Header-labeled blocks (### filename.py)
    for m in HEADER_PATTERN.finditer(text):
        _add(m.group(1), m.group(2), m.start(), m.end())

    # Pass 2: Comment-labeled blocks (# file: filename.py)
    for m in FILE_COMMENT_PATTERN.finditer(text):
        _add(m.group(1), m.group(2), m.start(), m.end())

    # Pass 3: If no labeled blocks found, try to infer from context
    if not blocks:
        # Look for filename mentions near code blocks
        # Pattern: "filename.py" or `filename.py` followed by a code block
        inline_pattern = re.compile(
            r'[`"]([a-zA-Z0-9_/\\.-]+\.py)[`"]\s*(?::|\n)'
            r'.*?```(?:python|py)?\s*\n(.*?)\n```',
            re.DOTALL
        )
        for m in inline_pattern.finditer(text):
            _add(m.group(1), m.group(2), m.start(), m.end())

    # Pass 4: Absolute fallback — unlabeled blocks
    if not blocks:
        generic_blocks = GENERIC_BLOCK_PATTERN.findall(text)
        if len(generic_blocks) == 1:
            # Single block, call it main.py
            blocks.append({
                "filename": "main.py",
                "content": generic_blocks[0].strip(),
            })
        elif len(generic_blocks) > 1:
            # Multiple unlabeled blocks — number them
            for i, content in enumerate(generic_blocks):
                content = content.strip()
                if not content:
                    continue
                # Try to guess filename from class/function names
                name = _guess_filename(content, i)
                blocks.append({
                    "filename": name,
                    "content": content,
                })

    return blocks


def _guess_filename(content: str, index: int) -> str:
    """Try to guess a reasonable filename from code content."""
    # Look for class definition
    class_match = re.search(r'^class\s+(\w+)', content, re.MULTILINE)
    if class_match:
        name = class_match.group(1)
        # CamelCase to snake_case
        snake = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        return f"{snake}.py"

    # Look for if __name__ == "__main__" — this is the entry point
    if '__name__' in content and '__main__' in content:
        return "main.py"

    # Look for def at top level
    func_match = re.search(r'^def\s+(\w+)', content, re.MULTILINE)
    if func_match:
        return f"{func_match.group(1)}.py"

    # Fallback
    return f"module_{index}.py"


def write_blocks_to_sandbox(blocks: list[dict]) -> list[dict]:
    """
    Write extracted code blocks to the sandbox workspace.

    Returns list of results from write_file calls.
    """
    results = []

    for block in blocks:
        filename = block["filename"]
        content = block["content"]

        # Ensure parent directories exist
        parent = str(Path(filename).parent)
        if parent and parent != ".":
            create_directory(parent)

        # If it's inside a package, ensure __init__.py exists
        parts = Path(filename).parts
        if len(parts) > 1:
            for i in range(len(parts) - 1):
                init_path = str(Path(*parts[:i+1]) / "__init__.py")
                # Only create if we're not already writing one
                if not any(b["filename"] == init_path for b in blocks):
                    write_file(init_path, "")

        result = write_file(filename, content)
        result["filename"] = filename
        results.append(result)

    return results


def process_coder_output(text: str) -> tuple[list[dict], list[dict]]:
    """
    Full pipeline: extract code blocks from Coder output and write to sandbox.

    Returns:
        (blocks, write_results)
    """
    blocks = extract_code_blocks(text)
    if not blocks:
        return [], []

    results = write_blocks_to_sandbox(blocks)
    return blocks, results
