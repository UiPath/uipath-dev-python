# Create Functions

Guide to creating UiPath coded functions — deterministic automation units for predictable, rule-based tasks.

## Initial Setup

When creating a new function:

1. **Setup pyproject.toml**:
   - Use the following `pyproject.toml` template if `pyproject.toml` doesn't exist in the function directory
   - Replace `{AGENT_NAME}` with the actual function name (lowercase, hyphenated)
   - Replace `{AGENT_DESCRIPTION}` with the function description you provide

   ```toml
   [project]
   name = "{AGENT_NAME}"
   version = "0.1.0"
   description = "{AGENT_DESCRIPTION}"
   readme = "README.md"
   requires-python = ">=3.11"
   dependencies = [
       "uipath",
   ]

   [dependency-groups]
   dev = [
       "uipath-dev",
   ]
   ```

2. **Install dependencies**: Run `uv sync` to install dependencies and create the virtual environment.

3. **Verify SDK**: Verify the UiPath SDK is available using `uv run uipath --version`.

All subsequent commands will be executed using `uv run` to ensure they run within the project's virtual environment. Authentication is already handled by the app — do not ask the user to authenticate.

## Project Configuration

### `uipath.json`

Create a `uipath.json` file in the project root to register your function entry points:

```json
{
  "functions": {
    "main": "main.py:main"
  }
}
```

The `"functions"` key maps function names to their entry points in `file:function` format.

### `bindings.json`

Create a `bindings.json` file in the project root to declare connections to UiPath resources (queues, buckets, etc.):

```json
{
  "bindings": []
}
```

Add entries as needed when your function interacts with UiPath platform resources.

## Workflow

### Step 1: Define Function Schema

Specify:
- **Function Description**: What does this function do?
- **Input Fields**: Name, type, description for each input parameter
- **Output Fields**: Name, type, description for each output

The schemas should be written as pydantic types.

### Step 2: Generate Template

The created function follows this structure:

```python
from pydantic import BaseModel, Field
from uipath.tracing import traced

class Input(BaseModel):
    # Generated fields based on your inputs
    pass

class Output(BaseModel):
    # Generated fields based on your outputs
    pass

@traced()
async def main(input: Input) -> Output:
    """Your function's business logic implementation."""
    # Implementation goes here
    pass
```

### Step 3: Implement Business Logic

Implement the main function with your deterministic logic. Use helper functions with tracing for sub-operations:

```python
from pydantic import BaseModel, Field
from uipath.tracing import traced

class Input(BaseModel):
    document_path: str = Field(description="Path to the document to process")

class Output(BaseModel):
    extracted_data: dict = Field(description="Extracted document data")

@traced(name="extract_fields", span_type="tool")
async def extract_fields(text: str) -> dict:
    """Helper function for field extraction."""
    # Deterministic extraction logic
    return {"field": "value"}

@traced()
async def main(input: Input) -> Output:
    """Process a document and extract structured data."""
    # Read document, extract fields, return results
    data = await extract_fields("document text")
    return Output(extracted_data=data)
```

### Step 4: Generate Entry Points

Run `uv run uipath init`. Doing so will generate:
- `entry-points.json` with JSON schemas
- Function structure and metadata

### Step 5: Local Testing

Run your function locally:

```bash
uv run uipath run main '{"document_path": "/path/to/doc"}'
```

See the [Running Agents](running-agents.md) guide for full details — the same `uv run uipath run` workflow applies to both agents and functions.

### Step 6: Pack & Publish

Package and deploy your function to UiPath Orchestrator:

```bash
# Create a deployable package (.nupkg)
uv run uipath pack

# Publish to personal workspace
uv run uipath publish -w

# OR publish to a specific tenant folder
uv run uipath publish -t
```

## Important Notes

- All functions are automatically traced for monitoring and debugging
- Input/output fields are strongly typed with Pydantic
- Generated `entry-points.json` enables integration with UiPath Cloud
- Functions use the `"functions"` key in `uipath.json` (not `"agents"`)
- Authentication is already handled by the app — do not ask the user to authenticate.

## Next Steps

Once your function is created, you can:
- **Run it**: Use the [Running Agents](running-agents.md) guide to execute with interactive inputs
- **Create Evaluations**: Use the [Creating Evaluations](evaluations/creating-evaluations.md) guide to build evaluation test cases
- **Run Evaluations**: Use the [Running Evaluations](evaluations/running-evaluations.md) guide to validate your function
