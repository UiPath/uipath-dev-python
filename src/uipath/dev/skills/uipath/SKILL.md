---
description: UiPath Coded Agents assistant - Create, run, and evaluate coded agents
allowed-tools: Bash, Read, Write, Glob, Grep
---

# UiPath Coded Agents Assistant

Welcome to the UiPath Coded Agents Assistant! This comprehensive guide helps you create, run, and evaluate UiPath coded agents using the UiPath Python SDK.

## Overview

The UiPath Coded Agents enables you to build intelligent automation agents with:
- **Type-safe agent definitions** using Pydantic models
- **Automatic tracing** for monitoring and debugging
- **Comprehensive testing** through evaluations
- **Cloud integration** with UiPath Orchestrator

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
  - Project setup with pyproject.toml
  - Schema definition with Pydantic models
  - Agent implementation
  - Entry point generation

- **[Tracing](references/tracing.md)** - Add monitoring and debugging
  - Basic tracing with `@traced()` decorator
  - Custom span names and run types
  - Data protection and privacy
  - Integration patterns
  - Common use cases
  - Viewing traces in Orchestrator

### Running Agents

Execute and test your agents:

- **[Running Agents](references/running-agents.md)** - Execute your agents
  - Agent discovery and selection
  - Interactive input collection
  - Execution and result display
  - Error handling

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

## Coded Agents Features

- **Type Safety**: Pydantic models ensure type-safe agent definitions
- **Automatic Tracing**: Monitor agent execution with `@traced()` decorator
- **Schema-Driven**: JSON schemas automatically generated from Pydantic models
- **Cloud Integration**: Seamless integration with UiPath Cloud Platform
- **Evaluation Framework**: Comprehensive testing with multiple evaluator types
- **Privacy**: Data redaction and sensitive field hiding

## Key Concepts

### Agents
Agents are reusable automation components that:
- Have well-defined input and output schemas
- Execute in the UiPath cloud or on-premise
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

3. **Testing your agents?**
   - Start with [Creating Evaluations](references/evaluations/creating-evaluations.md)
   - Review [Best Practices](references/evaluations/best-practices.md) for your agent type
   - Run evaluations with [Running Evaluations](references/evaluations/running-evaluations.md)

# Additional Instructions
- You MUST ALWAYS read the relevant linked references before making assumptions!
