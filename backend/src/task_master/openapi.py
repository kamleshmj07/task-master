"""Write the API's OpenAPI schema to a file, for generating client types.

Usage: `uv run python -m task_master.openapi <output.json>`
"""

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from task_master.config import Settings
from task_master.main import create_app

# Building the schema touches neither the database nor any secret.
PLACEHOLDER_SETTINGS = Settings(
    database_url=SecretStr("postgresql+asyncpg://unused@localhost/unused"),
    auth_secret=SecretStr("unused"),
)


def build_schema() -> dict[str, Any]:
    """Return the OpenAPI schema of the full app."""
    return create_app(PLACEHOLDER_SETTINGS).openapi()


def main(argv: list[str]) -> int:
    """Write the schema to the path in `argv`; return the exit code."""
    if len(argv) != 1:
        print("usage: python -m task_master.openapi <output.json>", file=sys.stderr)
        return 2
    output = Path(argv[0])
    schema = json.dumps(build_schema(), indent=2) + "\n"
    output.write_text(schema, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
