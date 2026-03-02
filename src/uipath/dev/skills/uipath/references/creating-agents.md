# Create Agents

Guide to creating new UiPath agents with AI-powered business logic implementation.

## Initial Setup

When creating a new agent:

1. **Setup pyproject.toml**:
   - Use the following `pyproject.toml` template if `pyproject.toml` doesn't exist in the agent directory
   - Replace `{AGENT_NAME}` with the actual agent name (lowercase, hyphenated)
   - Replace `{AGENT_DESCRIPTION}` with the agent description you provide
   - Add the appropriate framework dependency based on the agentic framework being used:
     - LangChain/LangGraph: add `"uipath-langchain"` to dependencies
     - LlamaIndex: add `"uipath-llamaindex"` to dependencies
     - OpenAI Agents SDK: add `"uipath-openai-agents"` to dependencies

   ```toml
   [project]
   name = "{AGENT_NAME}"
   version = "0.1.0"
   description = "{AGENT_DESCRIPTION}"
   readme = "README.md"
   requires-python = ">=3.11"
   dependencies = [
       "uipath",
       # Add the framework dependency based on the agentic framework:
       # "uipath-langchain",      # for LangChain / LangGraph agents
       # "uipath-llamaindex",     # for LlamaIndex agents
       # "uipath-openai-agents",  # for OpenAI Agents SDK agents
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

### Framework Config File

Register your agent entry points in the appropriate framework config file. The project may already have one — check which file has a non-empty `"agents"` key:

- `uipath.json` — default UiPath agents
- `pydantic_ai.json` — PydanticAI agents
- `langgraph.json` — LangGraph agents
- `llama_index.json` — LlamaIndex agents
- `google_adk.json` — Google ADK agents
- `openai_agents.json` — OpenAI Agents SDK agents

Format (all frameworks use the same structure):
```json
{
  "agents": {
    "agent_name": "main.py:agent"
  }
}
```

The `"agents"` key maps agent names to their entry points in `file:variable_or_function` format. **IMPORTANT**: If a config file already exists with agents defined, use that one — do NOT create a new config or add agents to a different config file.

### `bindings.json`

Create a `bindings.json` file in the project root to declare connections to UiPath resources (queues, buckets, etc.):

```json
{
  "bindings": []
}
```

Add entries as needed when your agent interacts with UiPath platform resources.

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

### Step 5: Pack & Publish

Package and deploy your agent to UiPath Orchestrator:

```bash
# Create a deployable package (.nupkg)
uv run uipath pack

# Publish to personal workspace
uv run uipath publish -w

# OR publish to a specific tenant folder
uv run uipath publish -t
```

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
- Authentication is already handled by the app — do not ask the user to authenticate.

## Next Steps

Once your agent is created, you can:
- **Run it**: Use the [Running Agents](../running-agents.md) guide to execute with interactive inputs
- **Create Evaluations**: Use the [Creating Evaluations](../evaluations/creating-evaluations.md) guide to build evaluation test cases
- **Run Evaluations**: Use the [Running Evaluations](../evaluations/running-evaluations.md) guide to validate your agent
