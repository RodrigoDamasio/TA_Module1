"""Static checks that keep the layering (DDD/DIP) and the SQL-injection controls in place."""

import ast
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

FORBIDDEN_IN_DOMAIN = {
    "fastapi",
    "pydantic",
    "starlette",
    "sqlite3",
    "app.api",
    "app.infrastructure",
    "app.application",
}


def _imported_modules(path: Path) -> set[str]:
    modules = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _violates(module: str, forbidden: set[str]) -> bool:
    return any(module == f or module.startswith(f + ".") for f in forbidden)


# T-A1
def test_domain_depends_on_nothing_but_the_standard_library():
    offenders = {
        f"{path.relative_to(APP)} imports {module}"
        for path in (APP / "domain").rglob("*.py")
        for module in _imported_modules(path)
        if _violates(module, FORBIDDEN_IN_DOMAIN)
    }
    assert offenders == set()


def test_application_does_not_depend_on_frameworks_or_infrastructure():
    forbidden = {"fastapi", "pydantic", "starlette", "sqlite3", "app.api", "app.infrastructure"}
    offenders = {
        f"{path.relative_to(APP)} imports {module}"
        for path in (APP / "application").rglob("*.py")
        for module in _imported_modules(path)
        if _violates(module, forbidden)
    }
    assert offenders == set()


# T-A2
def test_sqlite_is_only_used_in_infrastructure():
    users = {
        str(path.relative_to(APP))
        for path in APP.rglob("*.py")
        if "sqlite3" in _imported_modules(path)
    }
    assert users and all(u.startswith("infrastructure/") for u in users), users


# T-S4
def test_ruff_flags_sql_built_from_strings(tmp_path):
    bad = tmp_path / "bad_sql.py"
    bad.write_text(
        "def f(conn, x):\n    return conn.execute(f\"SELECT * FROM urls WHERE url = '{x}'\")\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "--select", "S608", str(bad)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "S608" in result.stdout
