# Create Agents

Guide to creating new UiPath agents with AI-powered business logic implementation.

## Initial Setup

When creating a new agent:

1. **Setup pyproject.toml**:
   - Use the official `pyproject.toml` template present in skill assets if `pyproject.toml` doesn't exist in the agent directory
   - Replace `{AGENT_NAME}` with the actual agent name
   - Replace `{AGENT_DESCRIPTION}` with the agent description you provide

2. **Install dependencies**: Run `uv sync` to install dependencies and create the virtual environment.

3. **Verify SDK**: Verify the UiPath SDK is available using `uv run uipath --version`.

4. **Authentication** (if needed): If any command requires authentication, run:
   ```bash
   uv run uipath auth --alpha
   ```

All subsequent commands will be executed using `uv run` to ensure they run within the project's virtual environment.

## Workflow

### Step 1: Define Agent Schema

Specify:
- **Agent Description**: What does this agent do?
- **Input Fields**: Name, type, description for each input parameter
- **Output Fields**: Name, type, description for each output

The schemas should be written as pydantic types.

### Step 2: Generate Template

The created agent follows this structure:

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
    """Your agent's business logic implementation."""
    # AI-implemented logic will go here
    pass
```

### Step 3: Implement Business Logic

Describe your agent's functionality, then implement the main function with:
- Proper error handling
- UiPath SDK method calls
- Input validation
- Output formatting

### Step 4: Generate Entry Points

Run `uv run uipath init`. Doing so will generate:
- `entry-points.json` with JSON schemas
- Documentation files (AGENTS.md, etc.)
- Agent structure and metadata

## Generated Template Details

The created agent will include:
- Pydantic models for Input and Output based on your schema
- UiPath SDK initialization
- `@traced()` decorator for monitoring
- Function signature with type hints

## Important Notes

- All agents are automatically traced for monitoring and debugging
- Input/output fields are strongly typed with Pydantic
- The agent works globally and can call any UiPath SDK services
- Generated `entry-points.json` enables integration with UiPath Cloud
- If you require authentication at any point, use `uv run uipath auth` to authenticate with UiPath. See the [Authentication guide](../authentication.md) for details.

## Next Steps

Once your agent is created, you can:
- **Run it**: Use the [Running Agents](../running-agents.md) guide to execute with interactive inputs
- **Create Evaluations**: Use the [Creating Evaluations](../evaluations/creating-evaluations.md) guide to build evaluation test cases
- **Run Evaluations**: Use the [Running Evaluations](../evaluations/running-evaluations.md) guide to validate your agent
