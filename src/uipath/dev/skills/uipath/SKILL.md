---
description: UiPath Coded Agents & Functions assistant - Create, run, and evaluate coded agents and functions
allowed-tools: Bash, Read, Write, Glob, Grep
---

# UiPath Coded Agents & Functions Assistant

Welcome to the UiPath Coded Agents & Functions Assistant! This comprehensive guide helps you create, run, and evaluate UiPath coded agents and coded functions using the UiPath Python SDK.

## Overview

The UiPath Python SDK enables you to build two types of coded automations:
- **Coded Agents** — AI-powered automation agents with LLM-driven decision-making
- **Coded Functions** — Simpler, deterministic automation units for predictable tasks

Both share:
- **Type-safe definitions** using Pydantic models
- **Automatic tracing** for monitoring and debugging
- **Comprehensive testing** through evaluations
- **Cloud integration** with UiPath Orchestrator
- **Pack & publish** workflow for deployment

## Documentation

### Building Agents

Develop new agents with monitoring and observability built-in:

- **[Creating Agents](references/creating-agents.md)** - Build new agents
  - Project setup with pyproject.toml and uipath.json
  - Schema definition with Pydantic models
  - Agent implementation
  - Entry point generation
  - Pack & publish

### Building Functions

Develop deterministic coded functions:

- **[Creating Functions](references/creating-functions.md)** - Build coded functions
  - Project setup with pyproject.toml and uipath.json
  - Schema definition with Pydantic models
  - Function implementation
  - Entry point generation
  - Pack & publish

### Observability

- **[Tracing](references/tracing.md)** - Add monitoring and debugging
  - Basic tracing with `@traced()` decorator
  - Custom span names and run types
  - Data protection and privacy
  - Integration patterns
  - Common use cases
  - Viewing traces in Orchestrator

### Running Agents & Functions

Execute and test your agents and functions:

- **[Running Agents](references/running-agents.md)** - Execute your agents and functions
  - Agent/function discovery and selection
  - Interactive input collection
  - Execution and result display
  - Error handling

### Deploying

Package and publish your agents and functions to UiPath Orchestrator:
- `uv run uipath pack` — Create a deployable package (.nupkg)
- `uv run uipath publish -w` — Publish to personal workspace
- `uv run uipath publish -t` — Publish to a specific tenant folder

### Testing & Evaluation

Ensure your agents work correctly with evaluations:

- **[Evaluations](references/evaluations.md)** — Creating evaluations, eval sets, running evaluations, mocking, best practices
- **[Evaluators](references/evaluators.md)** — All evaluator types, custom evaluators, selection guide

## Quick Patterns

### Calculator/Deterministic Agents
Use ExactMatch evaluators for agents that produce deterministic outputs.

### Natural Language Agents
Combine LLMJudge and Contains evaluators for semantic validation.

### Multi-Step Orchestration Agents
Use Trajectory and JsonSimilarity evaluators for multi-tool workflows.

### API Integration Agents
Mix JsonSimilarity and ExactMatch for API response validation.

## Features

- **Type Safety**: Pydantic models ensure type-safe definitions for agents and functions
- **Automatic Tracing**: Monitor execution with `@traced()` decorator
- **Schema-Driven**: JSON schemas automatically generated from Pydantic models
- **Cloud Integration**: Seamless integration with UiPath Cloud Platform
- **Evaluation Framework**: Comprehensive testing with multiple evaluator types
- **Pack & Publish**: Deploy agents and functions to Orchestrator
- **Privacy**: Data redaction and sensitive field hiding

## Key Concepts

### Agents
Agents are AI-powered automation components that:
- Have well-defined input and output schemas
- Use LLMs for decision-making and orchestration
- Are configured via `uipath.json` (`"agents"` key) or framework config files (e.g., `langgraph.json`)
- Are monitored and traced automatically
- Can be tested with evaluations

### Functions
Functions are deterministic automation units that:
- Have well-defined input and output schemas
- Execute predictable, rule-based logic without LLMs
- Are configured via `uipath.json` (`"functions"` key)
- Are monitored and traced automatically
- Can be tested with evaluations

### Evaluators
Evaluators validate agent behavior:
- **Output-Based**: Validate what the agent returns
- **Trajectory-Based**: Validate how the agent executes
- **Custom**: Implement domain-specific logic

### Evaluations
Evaluations are test suites that:
- Define test cases with inputs and expected outputs
- Use evaluators to score agent performance
- Support mocking external dependencies
- Track performance metrics

## Resources

- **UiPath Python SDK Documentation**: https://uipath.github.io/uipath-python/
- **UiPath Platform**: https://www.uipath.com/
- **Community**: Get help and share feedback with the UiPath community

## Next Steps

1. **Building your first agent?**
   - Start with [Creating Agents](references/creating-agents.md)
   - Learn about [Tracing](references/tracing.md) to add monitoring
   - Then run your first agent using [Running Agents](references/running-agents.md)

2. **Building your first function?**
   - Start with [Creating Functions](references/creating-functions.md)
   - Then run it using [Running Agents](references/running-agents.md) (same workflow)

3. **Testing your agents?**
   - Read [Evaluations](references/evaluations.md) for creating and running evaluations
   - Read [Evaluators](references/evaluators.md) for evaluator types and selection

# Additional Instructions
- You MUST ALWAYS read the relevant linked references before making assumptions!
