set quiet

default: lint format

lint:
    ruff check .
    python scripts/lint_httpx_client.py

format:
    ruff format --check .

validate: lint format

update-agents-md: validate
    python scripts/update_agents_md.py

build: update-agents-md
    uv build

install:
    uv sync --all-extras

# Test the custom linter
test-lint-httpx:
    python scripts/test_httpx_linter.py

# Validate server module (imports, serializers, app factory)
validate-server:
    python scripts/validate_server.py

# Validate frontend structure (no build)
validate-frontend:
    python scripts/validate_frontend.py

# Validate frontend structure + build
validate-frontend-build:
    python scripts/validate_frontend.py --build

# Run all validations (no frontend build)
validate-all: validate validate-server validate-frontend
