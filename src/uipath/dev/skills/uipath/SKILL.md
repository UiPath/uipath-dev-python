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

### Getting Started

Begin your agent development journey with these foundational topics:

- **[Authentication](references/authentication.md)** - Authenticate with UiPath
  - Interactive OAuth authentication
  - Unattended client credentials flow
  - Environment configuration
  - Network settings

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

- **[Evaluations](references/evaluations.md)** - Create and run evaluations
  - Output-based evaluators for result validation
  - Trajectory-based evaluators for execution flow analysis
  - Test case organization
  - Mocking external dependencies

- **[Creating Evaluations](references/evaluations/creating-evaluations.md)** - Design test cases
  - Define evaluation scenarios
  - Collect test inputs and expected outputs
  - Organize by scenario type
  - Schema validation

- **[Evaluators Guide](references/evaluations/evaluators/README.md)** - Understand evaluator types
  - Output-based evaluators (ExactMatch, JsonSimilarity, LLMJudgeOutput, Contains)
  - Trajectory-based evaluators (Trajectory)
  - Custom evaluators
  - Evaluator selection guide

- **[Evaluation Sets](references/evaluations/evaluation-sets.md)** - Structure your tests
  - Evaluation set file format
  - Test case schema
  - Mocking strategies
  - Complete examples

- **[Running Evaluations](references/evaluations/running-evaluations.md)** - Execute and analyze
  - Running test suites
  - Understanding results
  - Performance analysis
  - Troubleshooting

- **[Best Practices](references/evaluations/best-practices.md)** - Evaluation patterns
  - Best practices for evaluation design
  - Common patterns by agent type:
    - Calculator/Deterministic agents
    - Natural language agents
    - Multi-step orchestration agents
    - API integration agents
  - Test organization strategies
  - Performance optimization

## Quick Patterns

### Calculator/Deterministic Agents
Use ExactMatch evaluators for agents that produce deterministic outputs.
See [Best Practices - Calculator Pattern](references/evaluations/best-practices.md#pattern-1-calculatordeterministic-agents)

### Natural Language Agents
Combine LLMJudge and Contains evaluators for semantic validation.
See [Best Practices - Natural Language Pattern](references/evaluations/best-practices.md#pattern-2-natural-language-agents)

### Multi-Step Orchestration Agents
Use Trajectory and JsonSimilarity evaluators for multi-tool workflows.
See [Best Practices - Orchestration Pattern](references/evaluations/best-practices.md#pattern-3-multi-step-orchestration-agents)

### API Integration Agents
Mix JsonSimilarity and ExactMatch for API response validation.
See [Best Practices - API Integration Pattern](references/evaluations/best-practices.md#pattern-4-api-integration-agents)

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

1. **Getting started?**
   - See [Authentication](references/authentication.md) for setup instructions

2. **Building your first agent?**
   - Start with [Creating Agents](references/creating-agents.md)
   - Learn about [Tracing](references/tracing.md) to add monitoring
   - Then run your first agent using [Running Agents](references/running-agents.md)

3. **Building your first function?**
   - Start with [Creating Functions](references/creating-functions.md)
   - Then run it using [Running Agents](references/running-agents.md) (same workflow)

4. **Testing your agents?**
   - Start with [Creating Evaluations](references/evaluations/creating-evaluations.md)
   - Review [Best Practices](references/evaluations/best-practices.md) for your agent type
   - Run evaluations with [Running Evaluations](references/evaluations/running-evaluations.md)

# Additional Instructions
- You MUST ALWAYS read the relevant linked references before making assumptions!
