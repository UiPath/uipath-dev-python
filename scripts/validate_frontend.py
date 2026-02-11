"""Validate the frontend project: file structure, package.json, and build.

Run with: uv run python scripts/validate_frontend.py
Run with build: uv run python scripts/validate_frontend.py --build
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

FRONTEND_DIR = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "uipath"
    / "dev"
    / "server"
    / "frontend"
)
STATIC_DIR = FRONTEND_DIR.parent / "static"


def _check(label: str, fn):
    """Run a check function and report pass/fail."""
    try:
        fn()
        print(f"  PASS  {label}")
        return True
    except Exception as e:
        print(f"  FAIL  {label}: {e}")
        return False


def check_frontend_dir_exists():
    """Frontend source directory exists."""
    assert FRONTEND_DIR.exists(), f"Missing: {FRONTEND_DIR}"


def check_package_json():
    """package.json is valid and has required deps."""
    pkg_file = FRONTEND_DIR / "package.json"
    assert pkg_file.exists(), f"Missing: {pkg_file}"

    pkg = json.loads(pkg_file.read_text())
    assert "scripts" in pkg
    assert "build" in pkg["scripts"]
    assert "dev" in pkg["scripts"]

    deps = pkg.get("dependencies", {})
    assert "react" in deps, "Missing react dependency"
    assert "reactflow" in deps, "Missing reactflow dependency"
    assert "zustand" in deps, "Missing zustand dependency"
    assert "dagre" in deps, "Missing dagre dependency"


def check_vite_config():
    """vite.config.ts exists and has proxy config."""
    vite_cfg = FRONTEND_DIR / "vite.config.ts"
    assert vite_cfg.exists(), f"Missing: {vite_cfg}"
    content = vite_cfg.read_text()
    assert "/api" in content, "Missing API proxy config"
    assert "/ws" in content, "Missing WebSocket proxy config"


def check_tsconfig():
    """tsconfig.json exists."""
    assert (FRONTEND_DIR / "tsconfig.json").exists()


def check_index_html():
    """index.html exists with root div."""
    index = FRONTEND_DIR / "index.html"
    assert index.exists(), f"Missing: {index}"
    content = index.read_text()
    assert 'id="root"' in content, "Missing root div"


def check_source_structure():
    """Key source files exist."""
    src = FRONTEND_DIR / "src"
    assert src.exists(), f"Missing: {src}"

    required_files = [
        "main.tsx",
        "App.tsx",
        "api/client.ts",
        "api/websocket.ts",
        "store/useRunStore.ts",
        "store/useWebSocket.ts",
        "components/graph/GraphPanel.tsx",
        "components/traces/TraceTree.tsx",
        "components/chat/ChatPanel.tsx",
        "components/logs/LogPanel.tsx",
    ]

    missing = [f for f in required_files if not (src / f).exists()]
    assert not missing, f"Missing source files: {missing}"


def check_npm_available():
    """Check that npm is available on PATH."""
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    assert shutil.which(npm), f"{npm} not found on PATH"


def check_npm_install():
    """Verify npm install succeeds."""
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    result = subprocess.run(
        [npm, "install"],
        cwd=str(FRONTEND_DIR),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"npm install failed (exit {result.returncode}):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def check_npm_build():
    """Verify npm run build succeeds and produces static files."""
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    result = subprocess.run(
        [npm, "run", "build"],
        cwd=str(FRONTEND_DIR),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"npm run build failed (exit {result.returncode}):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    assert STATIC_DIR.exists(), f"Build did not produce {STATIC_DIR}"
    assert (STATIC_DIR / "index.html").exists(), "Build did not produce index.html"


def main():
    """Run frontend validation checks."""
    do_build = "--build" in sys.argv

    print("=" * 60)
    print(
        "Frontend Validation" + (" (with build)" if do_build else " (structure only)")
    )
    print("=" * 60)

    checks = [
        ("Frontend directory exists", check_frontend_dir_exists),
        ("package.json valid with required deps", check_package_json),
        ("vite.config.ts with proxy config", check_vite_config),
        ("tsconfig.json exists", check_tsconfig),
        ("index.html with root div", check_index_html),
        ("Source file structure complete", check_source_structure),
    ]

    if do_build:
        checks.extend(
            [
                ("npm available on PATH", check_npm_available),
                ("npm install succeeds", check_npm_install),
                ("npm run build succeeds", check_npm_build),
            ]
        )

    results = [_check(label, fn) for label, fn in checks]

    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} passed")

    if passed < total:
        sys.exit(1)
    else:
        print("All checks passed!")


if __name__ == "__main__":
    main()
