"""
Agent Mesh — File I/O Tools
────────────────────────────
Sandboxed file operations for agents.
All paths are validated against the sandbox root.
Nothing escapes the box.
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# ── Sandbox Configuration ─────────────────────────────────────────────────────

MESH_ROOT = Path("/media/ssd2/Local AI Build/agent-mesh")
SANDBOX_ROOT = MESH_ROOT / "sandbox"
WORKSPACE = SANDBOX_ROOT / "workspace"
ARCHIVE = SANDBOX_ROOT / "archive"
TEMP = SANDBOX_ROOT / "temp"
SKILLS = MESH_ROOT / "skills"  # read-only for agents (Phase 8)

# Max file size agents can write (1MB — prevents runaway generation)
MAX_FILE_SIZE = 1_048_576

# Allowed file extensions agents can create
ALLOWED_EXTENSIONS = {
    '.py', '.txt', '.md', '.json', '.yaml', '.yml',
    '.toml', '.cfg', '.ini', '.csv', '.sql', '.sh',
    '.html', '.css', '.js', '.xml', '.log',
}


# ── Sandbox Setup ─────────────────────────────────────────────────────────────

def init_sandbox():
    """Create sandbox directory structure if it doesn't exist."""
    for directory in [SANDBOX_ROOT, WORKSPACE, ARCHIVE, TEMP]:
        directory.mkdir(parents=True, exist_ok=True)

    # Create a marker file so we can verify sandbox integrity
    marker = SANDBOX_ROOT / ".sandbox_root"
    if not marker.exists():
        marker.write_text(f"Agent Mesh Sandbox — created {datetime.now().isoformat()}\n"
                          f"DO NOT place important files here. Agents write to this directory.\n")

    return True


# ── Path Validation ───────────────────────────────────────────────────────────

class SandboxViolation(Exception):
    """Raised when an operation attempts to escape the sandbox."""
    pass


def _validate_path(path: str, root: Path = WORKSPACE, allowed_roots: Optional[List[Path]] = None) -> Path:
    """
    Resolve and validate a path is within one of the allowed roots.
    Prevents directory traversal, symlink escapes, and out-of-bounds access.
    """
    # Resolve to absolute path (follows symlinks, resolves ..)
    target = Path(path).resolve() if Path(path).is_absolute() else (root / path).resolve()

    # If no explicit allowed roots, use a safe default (for internal calls)
    if allowed_roots is None:
        allowed_roots = [SANDBOX_ROOT.resolve()]

    # Normalise roots to absolute paths
    allowed_roots = [r.resolve() for r in allowed_roots]

    for allowed in allowed_roots:
        if str(target).startswith(str(allowed)):
            return target

    raise SandboxViolation(
        f"Path '{path}' resolves to '{target}' which is outside the allowed areas. "
        f"Permitted roots: {[str(r) for r in allowed_roots]}"
    )


def _validate_extension(path: Path):
    """Check file extension is allowed."""
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise SandboxViolation(
            f"Extension '{path.suffix}' is not allowed. "
            f"Permitted: {sorted(ALLOWED_EXTENSIONS)}"
        )


# ── File Operations (for agent use) ──────────────────────────────────────────

def write_file(filepath: str, content: str) -> dict:
    """
    Write content to a file inside the sandbox workspace.
    Creates parent directories as needed.

    Returns: {"success": bool, "path": str, "size": int, "error": str|None}
    """
    try:
        # Write operations are only allowed inside WORKSPACE
        target = _validate_path(filepath, root=WORKSPACE, allowed_roots=[WORKSPACE.resolve()])
        _validate_extension(target)

        if len(content) > MAX_FILE_SIZE:
            return {
                "success": False,
                "path": str(target),
                "size": 0,
                "error": f"Content exceeds max size ({len(content)} > {MAX_FILE_SIZE} bytes)"
            }

        # Ensure parent directories exist (still within WORKSPACE)
        parent = _validate_path(str(target.parent), root=WORKSPACE, allowed_roots=[WORKSPACE.resolve()])
        parent.mkdir(parents=True, exist_ok=True)

        target.write_text(content, encoding='utf-8')

        return {
            "success": True,
            "path": str(target),
            "size": len(content),
            "error": None
        }

    except SandboxViolation as e:
        return {"success": False, "path": filepath, "size": 0, "error": str(e)}
    except Exception as e:
        return {"success": False, "path": filepath, "size": 0, "error": f"Write failed: {e}"}


def read_file(filepath: str) -> dict:
    """
    Read a file from sandbox or skills directory.

    Returns: {"success": bool, "path": str, "content": str|None, "error": str|None}
    """
    try:
        allowed = [WORKSPACE.resolve()]
        if SKILLS.exists():
            allowed.append(SKILLS.resolve())
        target = _validate_path(filepath, root=WORKSPACE, allowed_roots=allowed)

        if not target.exists():
            return {"success": False, "path": str(target), "content": None, "error": "File not found"}

        if not target.is_file():
            return {"success": False, "path": str(target), "content": None, "error": "Not a file"}

        content = target.read_text(encoding='utf-8')

        return {
            "success": True,
            "path": str(target),
            "content": content,
            "error": None
        }

    except SandboxViolation as e:
        return {"success": False, "path": filepath, "content": None, "error": str(e)}
    except Exception as e:
        return {"success": False, "path": filepath, "content": None, "error": f"Read failed: {e}"}


def list_directory(dirpath: str = ".") -> dict:
    """
    List contents of a directory within the sandbox.

    Returns: {"success": bool, "path": str, "entries": list, "error": str|None}
    """
    try:
        allowed = [WORKSPACE.resolve()]
        if SKILLS.exists():
            allowed.append(SKILLS.resolve())
        target = _validate_path(dirpath, root=WORKSPACE, allowed_roots=allowed)

        if not target.exists():
            return {"success": False, "path": str(target), "entries": [], "error": "Directory not found"}

        if not target.is_dir():
            return {"success": False, "path": str(target), "entries": [], "error": "Not a directory"}

        entries = []
        for item in sorted(target.iterdir()):
            entries.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            })

        return {
            "success": True,
            "path": str(target),
            "entries": entries,
            "error": None
        }

    except SandboxViolation as e:
        return {"success": False, "path": dirpath, "entries": [], "error": str(e)}
    except Exception as e:
        return {"success": False, "path": dirpath, "entries": [], "error": f"List failed: {e}"}


def create_directory(dirpath: str) -> dict:
    """
    Create a directory within the sandbox workspace.

    Returns: {"success": bool, "path": str, "error": str|None}
    """
    try:
        target = _validate_path(dirpath, root=WORKSPACE, allowed_roots=[WORKSPACE.resolve()])
        target.mkdir(parents=True, exist_ok=True)

        return {"success": True, "path": str(target), "error": None}

    except SandboxViolation as e:
        return {"success": False, "path": dirpath, "error": str(e)}
    except Exception as e:
        return {"success": False, "path": dirpath, "error": f"Create dir failed: {e}"}


# ── Workspace Management ─────────────────────────────────────────────────────

def archive_workspace(job_id: str = "") -> dict:
    """
    Move current workspace contents to archive with timestamp.
    Creates a clean workspace for the next job.

    Returns: {"success": bool, "archive_path": str, "file_count": int, "error": str|None}
    """
    try:
        if not any(WORKSPACE.iterdir()):
            return {"success": True, "archive_path": "", "file_count": 0, "error": "Workspace empty, nothing to archive"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        label = f"{timestamp}_{job_id}" if job_id else timestamp
        archive_dest = ARCHIVE / label

        shutil.copytree(WORKSPACE, archive_dest)

        # Clean workspace
        for item in WORKSPACE.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

        file_count = sum(1 for _ in archive_dest.rglob("*") if _.is_file())

        return {
            "success": True,
            "archive_path": str(archive_dest),
            "file_count": file_count,
            "error": None
        }

    except Exception as e:
        return {"success": False, "archive_path": "", "file_count": 0, "error": f"Archive failed: {e}"}


def clean_temp() -> dict:
    """Clear the temp directory."""
    try:
        if TEMP.exists():
            for item in TEMP.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
        return {"success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": f"Clean temp failed: {e}"}


def get_workspace_summary() -> dict:
    """Get a summary of current workspace contents."""
    try:
        if not WORKSPACE.exists():
            return {"files": 0, "directories": 0, "total_size": 0, "tree": ""}

        files = list(WORKSPACE.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        dir_count = sum(1 for f in files if f.is_dir())
        total_size = sum(f.stat().st_size for f in files if f.is_file())

        # Build simple tree
        tree_lines = []
        for f in sorted(files):
            rel = f.relative_to(WORKSPACE)
            indent = "  " * (len(rel.parts) - 1)
            icon = "📁" if f.is_dir() else "📄"
            size = f" ({f.stat().st_size}b)" if f.is_file() else ""
            tree_lines.append(f"{indent}{icon} {f.name}{size}")

        return {
            "files": file_count,
            "directories": dir_count,
            "total_size": total_size,
            "tree": "\n".join(tree_lines)
        }

    except Exception as e:
        return {"files": 0, "directories": 0, "total_size": 0, "tree": f"Error: {e}"}


# ── Escape Tests (run these to verify containment) ───────────────────────────

def _run_escape_tests():
    """Verify sandbox containment — run these after any changes to path validation."""
    init_sandbox()

    tests = [
        # (description, should_fail, operation)
        ("Write inside workspace", False,
         lambda: write_file("test.py", "print('hello')")),
        ("Write to subdirectory", False,
         lambda: write_file("pkg/module.py", "# module")),
        ("Read own file", False,
         lambda: read_file("test.py")),
        ("List workspace", False,
         lambda: list_directory(".")),
        ("Escape via ../", True,
         lambda: write_file("../../etc/evil.py", "# evil")),
        ("Escape via absolute path", True,
         lambda: write_file("/etc/passwd", "# evil")),
        ("Escape via /tmp", True,
         lambda: write_file("/tmp/evil.py", "# evil")),
        ("Blocked extension .exe", True,
         lambda: write_file("malware.exe", "binary")),
        ("Blocked extension .so", True,
         lambda: write_file("exploit.so", "binary")),
        ("Write to mesh root", True,
         lambda: write_file("../server.py", "# overwrite server")),
    ]

    print("🔒 Sandbox Escape Tests")
    print("=" * 60)
    passed = 0
    failed = 0

    for desc, should_fail, op in tests:
        result = op()
        is_error = not result.get("success", True)

        if should_fail and is_error:
            print(f"  ✅ BLOCKED: {desc}")
            passed += 1
        elif not should_fail and not is_error:
            print(f"  ✅ ALLOWED: {desc}")
            passed += 1
        else:
            print(f"  ❌ WRONG:   {desc} (expected {'block' if should_fail else 'allow'}, got {'block' if is_error else 'allow'})")
            print(f"             {result}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} passed, {failed} failed")

    # Cleanup test files
    for f in ["test.py", "pkg/module.py", "pkg"]:
        p = WORKSPACE / f
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p)

    return failed == 0


if __name__ == "__main__":
    init_sandbox()
    print(f"Sandbox root:  {SANDBOX_ROOT}")
    print(f"Workspace:     {WORKSPACE}")
    print(f"Archive:       {ARCHIVE}")
    print(f"Temp:          {TEMP}")
    print()
    _run_escape_tests()
