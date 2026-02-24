# Write Evaluations

Create comprehensive test cases and execute evaluations for your UiPath agents using the UiPath evaluation framework.

## What is an Evaluation?

Evaluations assess agent performance by comparing actual outputs against expected results. The framework provides tools to create test cases, define evaluation criteria, and run comprehensive test suites.

## Two Types of Evaluators

**📊 Output-Based Evaluators** - Measure final results and validate outputs:
- ExactMatchEvaluator
- JsonSimilarityEvaluator
- LLMJudgeOutputEvaluator
- ContainsEvaluator

**🔄 Trajectory-Based Evaluators** - Examine execution patterns and decision sequences:
- TrajectoryEvaluator

## Documentation

### Detailed Guides

- **[Creating Evaluations](evaluations/creating-evaluations.md)**
  - Define evaluation details
  - Collect test cases
  - Organize by scenario (happy path, edge cases, errors)
  - Mock external calls

- **[Evaluators Guide](evaluations/evaluators/README.md)**
  - All available evaluator types
  - Configuration options
  - Choosing the right evaluator
  - Creating custom evaluators
  - Evaluation scoring

- **[Evaluation Sets](evaluations/evaluation-sets.md)**
  - Evaluation set file structure
  - Test case schema
  - Complete examples
  - Mocking strategies
  - Best practices for organization

- **[Running Evaluations](evaluations/running-evaluations.md)**
  - Execution configuration
  - Understanding results
  - Detailed analysis
  - Performance optimization
  - Troubleshooting

- **[Best Practices & Common Patterns](evaluations/best-practices.md)**
  - Evaluation best practices
  - Common patterns by agent type
  - Test organization strategies
  - Performance optimization
  - Quick reference guides

## Generated File Structure

```
evaluations/
├── eval-sets/
│   ├── <eval-name>.json
│   └── <another-eval>.json
└── evaluators/
    ├── exact-match.json
    ├── json-similarity.json
    └── llm-judge-semantic-similarity.json
```

## Common Patterns at a Glance

### Calculator/Deterministic Agents
```
Evaluators: ExactMatchEvaluator
Tests: Happy path, boundary values, error cases
Scoring: 1.0 (pass) or 0.0 (fail)
```
See [Best Practices](evaluations/best-practices.md#pattern-1-calculatordeterministic-agents)

### Natural Language Agents
```
Evaluators: LLMJudgeOutputEvaluator, ContainsEvaluator
Tests: Semantic equivalence, required keywords, various phrasings
Scoring: 0.0-1.0 range based on semantic similarity
```
See [Best Practices](evaluations/best-practices.md#pattern-2-natural-language-agents)

### Multi-Step Orchestration Agents
```
Evaluators: TrajectoryEvaluator, JsonSimilarityEvaluator
Tests: Tool sequences, decision flows, output structure
Scoring: 0.0-1.0 based on execution path and output match
```
See [Best Practices](evaluations/best-practices.md#pattern-3-multi-step-orchestration-agents)

### API Integration Agents
```
Evaluators: JsonSimilarityEvaluator, ExactMatchEvaluator
Tests: Success paths, error responses, mocked API calls
Scoring: 0.0-1.0 based on response structure match
```
See [Best Practices](evaluations/best-practices.md#pattern-4-api-integration-agents)

## Key Concepts

### Evaluation Scoring

All evaluators return numeric scores:
- **1.0** - Perfect pass
- **0.5-0.9** - Partial success (for similarity-based evaluators)
- **0.0** - Complete failure

Results also include justification, execution metrics, and complete traces.

### Test Case Organization

Organize tests by scenario:
- **Happy Path Tests** - Normal operations with typical inputs
- **Edge Case Tests** - Boundary values, empty/null values, large datasets
- **Error Scenario Tests** - Invalid inputs, missing fields, error handling

See [Creating Evaluations](evaluations/creating-evaluations.md#organizing-test-cases)

### Schema Validation

Evaluations are validated against:
- Agent's input schema from `entry-points.json`
- Agent's output schema from `entry-points.json`
- Required field constraints
- Type compatibility

## Mocking External Calls

Sometimes your agent calls external APIs or functions. You can mock these:

### Function Mocking
Mock specific function calls with return values or exceptions.

### LLM Call Mocking
Mock LLM interactions without making real API calls.

See [Evaluation Sets](evaluations/evaluation-sets.md#mocking-strategies) for detailed examples.

## Integration with UiPath Cloud

Results can be:
- Reported to UiPath Cloud for monitoring
- Integrated with CI/CD pipelines
- Compared with previous runs
- Used for performance tracking

## Best Practices

✅ **Do:**
- Use multiple evaluators for comprehensive validation
- Mix output-based and trajectory-based evaluators for complex agents
- Create separate eval sets for different scenarios (happy path, edge cases, errors)
- Use trajectory evaluators for agents with multiple steps/tools
- Use LLM evaluators for natural language or fuzzy matching scenarios
- Start with ExactMatch for deterministic outputs, then add LLM evaluators for flexibility

❌ **Don't:**
- Use only ExactMatch for natural language outputs
- Forget to test edge cases and error scenarios
- Use trajectory evaluators when output-based is sufficient
- Set too strict criteria early in development
- Skip schema validation during test creation

## Additional Resources

For detailed information about the evaluation framework, scoring, and advanced features:
https://uipath.github.io/uipath-python/eval/


---

# Creating Evaluations

This guide walks you through the process of creating comprehensive test cases for your UiPath agents.

## Overview

Creating evaluations involves defining test cases that validate your agent's behavior. Each evaluation set contains multiple test cases with inputs, expected outputs, and evaluation criteria.

## Workflow

### Phase 1: Setup Check

Before creating evaluations, ensure your project has:

- `uipath.json` - Project configuration
- `entry-points.json` - Agent definitions
- `evaluations/` directory for test cases

If missing, create an agent first. See the [Creating Agents](../../creating-agents.md) guide for setup instructions.

### Phase 2: Define Evaluation Details

You'll be asked for:

- **Evaluation Set Name** - Identifier for this evaluation set
- **Description** - What scenarios this covers
- **Target Agent** - Which agent to test
- **Number of Test Cases** - How many tests to create

### Phase 3: Collect Test Cases

For each test case, you'll guide through:

- **Inputs** - Based on agent's input schema with validation
- **Expected Output** - What the agent should return
- **Evaluation Criteria** - How to validate using available evaluators
- **Test Metadata** - ID, name, and purpose

## Test Metadata

Each test case requires:

- **id** - Unique identifier within the evaluation set
- **name** - Human-readable description of what this test validates
- **purpose** - What aspect of the agent is being tested

Good naming examples:
- `test-1-basic-addition` - Basic functionality test
- `test-2-large-numbers` - Boundary value test
- `test-3-negative-input` - Edge case test
- `test-4-invalid-type` - Error handling test

## Input Validation

Inputs are validated against your agent's input schema defined in `entry-points.json`:

- Required fields must be provided
- Values must match the expected types
- Complex objects follow their schema definitions

## Expected Output

Define what your agent should return:

- For simple outputs: a string or number
- For complex outputs: a JSON object matching your agent's output schema
- Multiple output fields can be specified

## Evaluation Criteria

Each test case can use multiple evaluators. For each evaluator, provide:

- **Evaluator ID** - Which evaluator to use (e.g., "ExactMatchEvaluator")
- **Evaluation-specific criteria** - Parameters for that evaluator

Examples:

**For ExactMatchEvaluator:**
```json
"expectedOutput": {
  "result": "5.0"
}
```

**For ContainsEvaluator:**
```json
"searchText": "success"
```

**For JsonSimilarityEvaluator:**
```json
"expectedOutput": {
  "result": 5.0,
  "status": "complete"
}
```

**For TrajectoryEvaluator:**
```json
"expectedAgentBehavior": "The agent should call the calculator tool once and return the result."
```

## Organizing Test Cases

Organize your test cases by scenario:

### Happy Path Tests

Tests for normal operations with typical inputs:
- Expected successful outcomes
- Standard use cases
- Typical input ranges

Example: A calculator agent being given two positive numbers to add.

### Edge Case Tests

Tests for boundary conditions and unusual inputs:
- Boundary values (0, min, max)
- Empty/null values
- Large datasets
- Special characters
- Single vs. multiple items

Example: Calculator with zero, negative numbers, very large numbers.

### Error Scenario Tests

Tests for invalid inputs and error handling:
- Invalid input types
- Missing required fields
- Out-of-range values
- Expected error messages
- Handling of malformed data

Example: Calculator given non-numeric input or invalid format.

## Best Practices for Test Cases

### Be Specific

❌ Bad: "test-output" - vague, doesn't describe what's being tested

✅ Good: "test-large-json-output" - clear about what scenario is tested

### Test One Thing Per Case

❌ Bad: Testing multiple scenarios in one test case

✅ Good: Separate tests for each distinct scenario

### Use Realistic Data

❌ Bad: Generic placeholder values like "value1", "value2"

✅ Good: Realistic inputs based on actual use cases

### Cover the Input Space

- Test normal/common cases
- Test boundary conditions
- Test error conditions
- Test different input combinations

### Validate Multiple Aspects

❌ Bad: Only checking the main output field

✅ Good: Using multiple evaluators to validate:
- Output correctness (ExactMatchEvaluator)
- Response structure (JsonSimilarityEvaluator)
- Execution flow (TrajectoryEvaluator)

## File Organization

Tests are organized in the `evaluations/` directory:

```
evaluations/
├── eval-sets/
│   ├── happy-path.json
│   ├── edge-cases.json
│   └── error-scenarios.json
└── evaluators/
    ├── exact-match.json
    ├── json-similarity.json
    └── llm-judge-semantic-similarity.json
```

Evaluators are reusable across multiple evaluation sets. Reference them by their ID in your eval sets.

## Schema Validation

Your test inputs are validated against:

- Agent's input schema from `entry-points.json`
- Agent's output schema from `entry-points.json`
- Required field constraints
- Type compatibility

This ensures test cases are valid before execution.

## Mocking External Calls

Sometimes your agent calls external APIs or functions. You can mock these for testing:

### Function Mocking

Mock specific function calls with return values or exceptions:

```json
"mockingStrategy": {
  "type": "mockito",
  "behaviors": [
    {
      "function": "external_api_call",
      "arguments": {
        "args": ["param1"],
        "kwargs": {"key": "value"}
      },
      "then": [
        {
          "type": "return",
          "value": {
            "status": "success",
            "data": "mocked-response"
          }
        }
      ]
    }
  ]
}
```

**Mock Behavior Types:**
- `type: "return"` - Return a value
- `type: "raise"` - Throw an exception

### LLM Call Mocking

Mock LLM interactions for testing without API calls:

```json
"mockingStrategy": {
  "type": "llm",
  "prompt": "Test prompt describing the expected LLM behavior",
  "toolsToSimulate": [
    {
      "name": "tool_name"
    }
  ]
}
```

## Next Steps

After creating evaluation sets, you can:

1. **Run Evaluations** - Execute tests to see how your agent performs
2. **Create More Sets** - Add additional test scenarios
3. **View Details** - Examine specific test results
4. **Export Results** - Save results for analysis

See [Running Evaluations](running-evaluations.md) for execution details.


---

# Evaluation Sets

Evaluation sets define test cases and organize them with their evaluation criteria. This guide covers the structure and creation of evaluation set files.

## What is an Evaluation Set?

An evaluation set is a JSON file containing:

- **Metadata** - Name, description, version information
- **Evaluator References** - Which evaluators this set uses
- **Test Cases** - Individual evaluations with inputs and criteria
- **Optional Mocking** - Mock external calls for isolated testing

## File Location

Evaluation sets are stored in:

```
evaluations/eval-sets/
```

Create one JSON file per evaluation set. Example:

```
evaluations/
├── eval-sets/
│   ├── happy-path-scenarios.json
│   ├── edge-cases.json
│   ├── error-scenarios.json
│   └── performance-tests.json
└── evaluators/
    ├── exact-match.json
    ├── json-similarity.json
    └── ...
```

## Basic Schema

```json
{
  "version": "1.0",
  "id": "my-eval-set",
  "name": "My Evaluation Set",
  "description": "Description of what this eval set tests",
  "evaluatorRefs": ["EvaluatorId1", "EvaluatorId2"],
  "evaluations": [
    {
      "id": "test-1",
      "name": "Test case name",
      "inputs": {
        "param1": "value1",
        "param2": 42
      },
      "evaluationCriterias": {
        "EvaluatorId1": {
          // Evaluator-specific criteria
        }
      }
    }
  ]
}
```

## Top-Level Fields

### version

The schema version. Currently: `"1.0"`

### id

Unique identifier for this evaluation set. Used internally and in references.

Examples: `"happy-path"`, `"edge-cases"`, `"calculator-tests"`

### name

Human-readable name for the evaluation set.

Example: `"Happy Path Scenarios"`, `"Calculator Edge Cases"`

### description

(Optional) Longer description of what this evaluation set covers.

Example: `"Tests basic calculator operations with standard inputs"`

### evaluatorRefs

Array of evaluator IDs that this eval set uses.

These must match the `id` field of evaluators in `evaluations/evaluators/`.

Example:
```json
"evaluatorRefs": ["ExactMatchEvaluator", "JsonSimilarityEvaluator"]
```

### evaluations

Array of test cases. See "Test Case Structure" below.

## Test Case Structure

Each test case in the `evaluations` array has this structure:

```json
{
  "id": "test-1-basic",
  "name": "Basic test case",
  "inputs": {
    "param1": "value1",
    "param2": 42
  },
  "evaluationCriterias": {
    "ExactMatchEvaluator": {
      "expectedOutput": {
        "result": "expected-value"
      }
    },
    "JsonSimilarityEvaluator": {
      "expectedOutput": {
        "result": "expected-value"
      }
    }
  },
  "mockingStrategy": {}  // optional
}
```

### Test Case Fields

#### id

Unique identifier within this evaluation set.

Convention: `test-<number>-<scenario>` or `<scenario>-<variant>`

Examples:
- `test-1-basic`
- `test-2-large-input`
- `test-3-empty-field`
- `calculator-add`
- `calculator-subtract`

#### name

Human-readable description of the test case.

Examples:
- "Basic addition test"
- "Addition with large numbers"
- "Empty input handling"

#### inputs

Input parameters for the agent. Must match the agent's input schema.

```json
"inputs": {
  "num1": 5,
  "num2": 3,
  "operation": "add"
}
```

For complex inputs with nested objects:

```json
"inputs": {
  "user": {
    "id": "123",
    "name": "John Doe"
  },
  "filters": {
    "status": "active",
    "role": "admin"
  }
}
```

#### evaluationCriterias

Map of evaluator ID to evaluation criteria for that evaluator.

Each evaluator has different required fields:

**ExactMatchEvaluator:**
```json
"ExactMatchEvaluator": {
  "expectedOutput": {
    "result": "5.0"
  }
}
```

**ContainsEvaluator:**
```json
"ContainsEvaluator": {
  "searchText": "success"
}
```

**JsonSimilarityEvaluator:**
```json
"JsonSimilarityEvaluator": {
  "expectedOutput": {
    "result": 5.0,
    "status": "complete"
  }
}
```

**TrajectoryEvaluator:**
```json
"TrajectoryEvaluator": {
  "expectedAgentBehavior": "The agent should call the calculator tool once and return the sum."
}
```

**LLMJudge Evaluators:**
```json
"LLMJudgeOutputEvaluator": {
  "expectedOutput": {
    "result": "A helpful response"
  }
}
```

See [Evaluators Guide](evaluators.md) for detailed field documentation.

#### mockingStrategy (optional)

Mock external function calls or LLM interactions. Two types:

### Function Mocking (mockito)

```json
"mockingStrategy": {
  "type": "mockito",
  "behaviors": [
    {
      "function": "external_api_call",
      "arguments": {
        "args": ["param1"],
        "kwargs": {"key": "value"}
      },
      "then": [
        {
          "type": "return",
          "value": {
            "status": "success",
            "data": "mocked-response"
          }
        }
      ]
    },
    {
      "function": "another_function",
      "arguments": {
        "args": [],
        "kwargs": {}
      },
      "then": [
        {
          "type": "raise",
          "value": {
            "_target_": "ValueError"
          }
        }
      ]
    }
  ]
}
```

**Mock Behavior Types:**
- `type: "return"` - Return a value
- `type: "raise"` - Throw an exception

### LLM Call Mocking

```json
"mockingStrategy": {
  "type": "llm",
  "prompt": "Test prompt describing the expected LLM behavior",
  "toolsToSimulate": [
    {
      "name": "tool_name"
    },
    {
      "name": "another_tool"
    }
  ]
}
```

## Complete Examples

### Simple Calculator Test Set

```json
{
  "version": "1.0",
  "id": "calculator-basic",
  "name": "Calculator Basic Tests",
  "description": "Basic tests for calculator agent with happy path and simple edge cases",
  "evaluatorRefs": ["ExactMatchEvaluator"],
  "evaluations": [
    {
      "id": "test-1-add",
      "name": "Basic addition",
      "inputs": {
        "num1": 5,
        "num2": 3
      },
      "evaluationCriterias": {
        "ExactMatchEvaluator": {
          "expectedOutput": {
            "result": "8"
          }
        }
      }
    },
    {
      "id": "test-2-subtract",
      "name": "Basic subtraction",
      "inputs": {
        "num1": 10,
        "num2": 4
      },
      "evaluationCriterias": {
        "ExactMatchEvaluator": {
          "expectedOutput": {
            "result": "6"
          }
        }
      }
    },
    {
      "id": "test-3-zero",
      "name": "Edge case with zero",
      "inputs": {
        "num1": 0,
        "num2": 5
      },
      "evaluationCriterias": {
        "ExactMatchEvaluator": {
          "expectedOutput": {
            "result": "5"
          }
        }
      }
    }
  ]
}
```

### Complex Agent Test Set with Mocking

```json
{
  "version": "1.0",
  "id": "api-agent-tests",
  "name": "API Agent Tests",
  "description": "Tests for agent that calls external APIs with mocked responses",
  "evaluatorRefs": ["JsonSimilarityEvaluator", "ExactMatchEvaluator"],
  "evaluations": [
    {
      "id": "test-1-fetch-user",
      "name": "Fetch user data from API",
      "inputs": {
        "userId": "123"
      },
      "evaluationCriterias": {
        "JsonSimilarityEvaluator": {
          "expectedOutput": {
            "id": "123",
            "name": "John Doe",
            "email": "john@example.com"
          }
        }
      },
      "mockingStrategy": {
        "type": "mockito",
        "behaviors": [
          {
            "function": "fetch_user_from_api",
            "arguments": {
              "args": ["123"],
              "kwargs": {}
            },
            "then": [
              {
                "type": "return",
                "value": {
                  "id": "123",
                  "name": "John Doe",
                  "email": "john@example.com"
                }
              }
            ]
          }
        ]
      }
    },
    {
      "id": "test-2-api-error",
      "name": "Handle API error",
      "inputs": {
        "userId": "invalid"
      },
      "evaluationCriterias": {
        "ExactMatchEvaluator": {
          "expectedOutput": {
            "error": "User not found"
          }
        }
      },
      "mockingStrategy": {
        "type": "mockito",
        "behaviors": [
          {
            "function": "fetch_user_from_api",
            "arguments": {
              "args": ["invalid"],
              "kwargs": {}
            },
            "then": [
              {
                "type": "raise",
                "value": {
                  "_target_": "Exception",
                  "args": ["User not found"]
                }
              }
            ]
          }
        ]
      }
    }
  ]
}
```

### Multi-Evaluator Test Set

```json
{
  "version": "1.0",
  "id": "summarizer-comprehensive",
  "name": "Document Summarizer Comprehensive Tests",
  "description": "Comprehensive tests using multiple evaluators for document summarization agent",
  "evaluatorRefs": [
    "ExactMatchEvaluator",
    "ContainsEvaluator",
    "LLMJudgeOutputEvaluator"
  ],
  "evaluations": [
    {
      "id": "test-1-summary-quality",
      "name": "Check summary contains key points",
      "inputs": {
        "document": "The quick brown fox jumps over the lazy dog. This is an important animal behavior study.",
        "maxLength": 50
      },
      "evaluationCriterias": {
        "ContainsEvaluator": {
          "searchText": "fox"
        },
        "ContainsEvaluator": {
          "searchText": "jumps"
        },
        "LLMJudgeOutputEvaluator": {
          "expectedOutput": {
            "summary": "A concise summary capturing the main idea"
          }
        }
      }
    }
  ]
}
```

## Referencing Evaluators

Evaluators are referenced by their `id` field in the evaluator definition.

If you have an evaluator file `evaluations/evaluators/exact-match.json` with:

```json
{
  "id": "ExactMatchEvaluator",
  ...
}
```

Reference it in your eval set as:

```json
"evaluatorRefs": ["ExactMatchEvaluator"]
```

## Best Practices

- **Use Descriptive IDs** - Make test IDs self-documenting
- **Group Related Tests** - Put similar tests in the same eval set
- **Reuse Evaluators** - Create evaluator files once, reference in multiple eval sets
- **Comment Complex Inputs** - For complex test inputs, add context in the test name
- **Version Your Eval Sets** - Use semantic versioning in eval set IDs as they evolve
- **Document Edge Cases** - Make test names clear about what edge case is being tested

## Next Steps

- [Running Evaluations](running-evaluations.md) - Execute your evaluation sets
- [Evaluators Guide](evaluators.md) - Learn more about evaluator types
- [Creating Evaluations](creating-evaluations.md) - Workflow for creating test cases


---

# Running Evaluations

This guide covers how to execute your evaluation sets and understand the results.

## Getting Started

### Evaluation Discovery

When you run evaluations, the system will scan for evaluation sets in:

```
evaluations/eval-sets/*.json
```

Example display:

```
AVAILABLE EVALUATIONS
═════════════════════════════════════════════════════════

1. evaluations/eval-sets/happy-path-scenarios.json
   └─ Tests: 3 | Last run: 2 hours ago

2. evaluations/eval-sets/edge-cases.json
   └─ Tests: 5 | Last run: Never

3. evaluations/eval-sets/error-scenarios.json
   └─ Tests: 4 | Last run: 1 day ago
```

### Execution Configuration

Before running, you'll be asked for:

- **Evaluation Set** - Which eval set to run
- **Number of Workers** - Parallel execution (1-8, default: 4)
- **Enable Mocker Cache** - Cache LLM responses for reproducibility (default: False)
- **Report to Studio** - Send results to UiPath Cloud (optional, default: False)

## Running Evaluations

### Command

```bash
uv run uipath eval <entrypoint> <eval-file> \
  --workers 4 \
  --no-report \
  --output-file eval-results.json
```

**Parameters:**
- `<entrypoint>` - Agent entry point name from `entry-points.json`
- `<eval-file>` - Path to evaluation set file
- `--workers` - Number of parallel workers (1-8)
- `--no-report` - Don't report to UiPath Cloud
- `--output-file` - Save results to JSON file

## Understanding Results

### Result Format

Each test case produces:

```
Test: calculate_sum
├─ Input: {"num1": 5, "num2": 3}
├─ Expected Output: {"result": 8}
├─ Actual Output: {"result": 8}
├─ ExactMatchEvaluator: PASS (1.0) - Output exactly matches expected
├─ JsonSimilarityEvaluator: PASS (1.0) - JSON structure identical
└─ Execution Time: 125ms
```

### Numeric Scores

All evaluators return scores:

- **1.0** - Perfect pass (evaluator criteria fully met)
- **0.5-0.9** - Partial success (similarity-based evaluators show partial match)
- **0.0** - Complete failure (evaluator criteria not met)

### Score Interpretation

**For ExactMatchEvaluator & ContainsEvaluator:**
- 1.0 - Requirement met
- 0.0 - Requirement not met

**For Similarity-Based Evaluators (JSON, LLM Judge, Trajectory):**
- 1.0 - Perfect match
- 0.9-0.5 - Good match with minor differences
- 0.4-0.1 - Weak match with significant differences
- 0.0 - No match

## Detailed Results

### Results Display

Results include:

- **Numeric Scores** - 0.0-1.0 range for each test and evaluator
- **Detailed Justification** - Why each evaluator gave that score
- **Execution Metrics** - Test execution time and performance data
- **Complete Traces** - Full execution history including function calls and state changes

### Example Detailed Result

```json
{
  "testId": "test-1-basic",
  "testName": "Basic addition test",
  "status": "PASSED",
  "input": {
    "num1": 5,
    "num2": 3
  },
  "expectedOutput": {
    "result": 8
  },
  "actualOutput": {
    "result": 8
  },
  "evaluationResults": [
    {
      "evaluatorId": "ExactMatchEvaluator",
      "score": 1.0,
      "status": "PASSED",
      "justification": "Output exactly matches expected value",
      "executionTime": 45
    },
    {
      "evaluatorId": "JsonSimilarityEvaluator",
      "score": 1.0,
      "status": "PASSED",
      "justification": "JSON structure and values are identical",
      "executionTime": 52
    }
  ],
  "totalExecutionTime": 125,
  "agentExecutionTrace": {
    "steps": [
      {
        "type": "tool_call",
        "toolName": "calculator",
        "arguments": {"a": 5, "b": 3},
        "result": 8
      }
    ]
  }
}
```

## Pass vs Fail

### Determining Overall Test Status

A test passes if:

- All required evaluators produce their expected scores
- Output matches criteria for pass-fail evaluators (ExactMatch, Contains)
- Similarity scores are above your acceptance threshold

A test fails if:

- Any evaluator criteria are not met
- Output doesn't match for ExactMatch or Contains evaluators
- Similarity scores are below acceptable thresholds

### Example Breakdown

```
RESULTS SUMMARY
═════════════════════════════════════════════════════════

Total Tests: 5
Passed: 4 (80%)
Failed: 1 (20%)

FAILED TESTS
─────────────────────────────────────────────────────────

Test: test-2-edge-case (Edge case with zero)
Input: {"num1": 0, "num2": 5}
Expected: {"result": 5}
Actual: {"result": "5"}
├─ ExactMatchEvaluator: FAIL (0.0)
│  └─ Reason: Expected number but got string
└─ Suggestion: Ensure output type matches schema

PASSED TESTS
─────────────────────────────────────────────────────────

Test: test-1-basic → PASS (1.0)
Test: test-3-large → PASS (1.0)
Test: test-4-negative → PASS (1.0)
Test: test-5-decimal → PASS (1.0)
```

## Analyzing Results

### For Each Failing/Warning Test

The system shows:

1. **Input/Output Pairs**
   - Exact inputs used
   - Expected vs actual results

2. **Evaluator Scores and Justification**
   - Score from each evaluator
   - Explanation of the score
   - Why it passed or failed

3. **Execution Traces**
   - Full execution history
   - Function calls made
   - State changes during execution
   - Timing information

4. **Suggestions for Fixes**
   - Identified issues
   - Recommended changes
   - Best practices for similar cases

### Example Detailed Analysis

```
FAILING TEST ANALYSIS
═════════════════════════════════════════════════════════

Test ID: test-3-invalid-type
Test Name: Invalid input type handling
Status: FAILED

Input Provided:
{
  "value": "not-a-number"  // Should have been numeric
}

Expected Output:
{
  "error": "Invalid input type"
}

Actual Output:
{
  "result": null,
  "error": null
}

Evaluation Results:
─────────────────────────────────────────────────────────

1. ExactMatchEvaluator (Score: 0.0 - FAILED)
   Justification: Expected error message was not returned

2. JsonSimilarityEvaluator (Score: 0.3 - FAILED)
   Justification: 30% similarity. Has 'error' field but value differs.

Execution Trace:
─────────────────────────────────────────────────────────

1. [0ms] Function called: validate_input
   Arguments: {"value": "not-a-number"}
   Result: {"valid": false, "error": "Not numeric"}

2. [5ms] Function called: process_value
   Arguments: {"value": "not-a-number"}
   Result: null
   Note: Process function called despite validation failure

3. [8ms] Return result
   Final Output: {"result": null, "error": null}

Recommendations:
─────────────────────────────────────────────────────────

✓ Check validation logic in validate_input function
✓ Return error when validation fails instead of processing
✓ Ensure error handling is consistent across all paths
✓ Consider adding type checking at entry point
```

## Follow-up Actions

After running evaluations, you can:

### Create More Evaluations

Add additional evaluation sets for:
- Different scenarios
- New test cases
- Additional edge cases

### Fix Issues

I can help:
- Modify agent code to fix failing tests
- Update evaluation criteria if needed
- Improve error handling

### Re-run Evaluations

Execute with different configurations:
- Different number of workers
- Different evaluation sets
- With/without mocking

### View Details

Examine detailed information:
- Individual test results
- Execution traces
- Performance metrics
- Failure analysis

### Export Results

Save results for:
- External analysis
- CI/CD integration
- Performance tracking
- Trend analysis

### Compare Runs

Track improvements:
- Compare current run with previous runs
- View score trends over time
- Identify regressions
- Monitor performance changes

## Integration with UiPath Cloud

Results can be:

- **Reported to UiPath Cloud** - for monitoring and analytics
- **Integrated with CI/CD pipelines** - for automated testing
- **Compared with previous runs** - for trend tracking
- **Used for performance tracking** - across versions

Set `--report` flag to send results to your UiPath Cloud account:

```bash
uv run uipath eval <entrypoint> <eval-file> \
  --report \
  --workers 4
```

## Performance Optimization

### Using Parallel Workers

Run tests in parallel for faster execution:

```bash
uv run uipath eval <entrypoint> <eval-file> \
  --workers 8
```

**Worker count recommendations:**
- `1` - Sequential, useful for debugging
- `4` - Default, good balance
- `8` - Maximum, for large evaluation sets

### Caching LLM Responses

For evaluators using LLMs (LLMJudge, Trajectory), enable mocker cache:

```bash
uv run uipath eval <entrypoint> <eval-file> \
  --mocker-cache
```

Benefits:
- Faster execution on re-runs
- Reproducible results
- Lower API costs
- Useful for CI/CD pipelines

## Troubleshooting

### Test Passes but Score Seems Wrong

- Check evaluator configuration
- Review evaluation criteria
- Verify expected output format
- Look at justification in detailed results

### All Tests Fail

- Verify agent is working correctly
- Check evaluation set references correct agent
- Ensure evaluator files exist and are valid
- Review agent input/output schemas

### Performance Issues

- Reduce number of workers if hitting rate limits
- Enable mocker cache for LLM evaluators
- Run subset of tests first to debug
- Check for slow external API calls

### LLM Evaluator Issues

- Verify API credentials are configured
- Check model name is valid
- Review prompt template syntax
- Enable cache to reduce API calls

## Best Practices

✅ **Do:**
- Run evaluations regularly during development
- Start with small evaluation sets, expand gradually
- Use multiple evaluators for comprehensive validation
- Cache LLM responses in CI/CD pipelines
- Review detailed traces for failing tests
- Track score trends over time

❌ **Don't:**
- Run with too many workers without testing first
- Skip detailed result analysis for failures
- Ignore justification messages from evaluators
- Set unrealistic expectations too early
- Run expensive LLM evaluators without caching

## Next Steps

- [Creating Evaluations](creating-evaluations.md) - Create more test cases
- [Evaluators Guide](evaluators.md) - Learn about evaluator types
- [Evaluation Sets](evaluation-sets.md) - Structure evaluation set files
- [Best Practices](best-practices.md) - Tips for effective testing


---

# Best Practices & Common Patterns

This guide covers best practices for effective evaluation design and common patterns for different agent types.

## Evaluation Best Practices

### Do ✅

- **Use multiple evaluators** for comprehensive validation
  - Don't rely on a single evaluator
  - Combine output-based and trajectory-based evaluators for complex agents
  - Example: Use both ExactMatchEvaluator and JsonSimilarityEvaluator

- **Create separate eval sets for different scenarios**
  - Happy path scenarios
  - Edge cases
  - Error scenarios
  - Performance tests
  - This makes it easier to maintain and debug

- **Mix evaluator types appropriately**
  - Output-based evaluators for result validation
  - Trajectory evaluators for multi-step agents
  - LLM evaluators for natural language outputs

- **Use trajectory evaluators for multi-step agents**
  - Validates execution flow and tool usage
  - Ensures agent takes expected decision paths
  - Useful for orchestration agents

- **Use LLM evaluators for natural language or fuzzy matching**
  - Better for semantic equivalence
  - More flexible than exact matching
  - Handles variations in wording

- **Start with ExactMatch, then add flexibility**
  - Begin with strict ExactMatchEvaluator during development
  - Add LLM evaluators for production as needed
  - Allows refinement as agent matures

- **Mock external dependencies consistently**
  - Mock all external API calls
  - Use mocking for deterministic testing
  - Cache LLM responses in CI/CD

- **Version your evaluation sets**
  - Use semantic versioning in IDs
  - Track changes over time
  - Example: `calculator-v1`, `calculator-v2`

- **Document test purposes clearly**
  - Use descriptive test names
  - Explain what each test validates
  - Make it easy for others to understand

- **Review failed tests carefully**
  - Examine execution traces
  - Understand why tests failed
  - Fix either the agent or test expectations

### Don't ❌

- **Use only ExactMatch for natural language outputs**
  - Too strict, fails on minor variations
  - Use LLMJudgeOutputEvaluator instead

- **Forget to test edge cases and error scenarios**
  - Test boundary values (0, min, max)
  - Test empty/null values
  - Test invalid inputs

- **Use trajectory evaluators when output-based is sufficient**
  - Trajectory evaluation is more expensive
  - Only use when execution path matters
  - For simple agents, output validation is enough

- **Set too strict criteria early in development**
  - Allow flexibility while agent is evolving
  - Tighten criteria as agent stabilizes
  - Start with 80%, improve to 95%+

- **Skip schema validation during test creation**
  - Always validate inputs against schema
  - Prevents invalid test data
  - Catches type mismatches early

- **Mix unrelated tests in one eval set**
  - Keep eval sets focused and organized
  - Separate happy path from error cases
  - Makes debugging easier

- **Use generic evaluator IDs**
  - Don't use generic names like "evaluator1"
  - Use descriptive names: "SumCalculatorEvaluator"
  - Makes eval sets self-documenting

- **Ignore performance metrics**
  - Monitor execution times
  - Track performance trends
  - Identify bottlenecks

## Common Evaluation Patterns

### Pattern 1: Calculator/Deterministic Agents

For agents that always produce the same output for the same input:

**Test Organization:**
```
eval-sets/
├── calculator-happy-path.json       # Normal operations
├── calculator-edge-cases.json       # Boundary values
└── calculator-error-cases.json      # Invalid inputs
```

**Evaluator Selection:**
- **Primary:** ExactMatchEvaluator
- **Secondary:** (optional) JsonSimilarityEvaluator for complex outputs

**Test Cases:**
```
Happy Path:
- Basic addition, subtraction, multiplication, division
- Standard values (1-100)

Edge Cases:
- Zero values
- Negative numbers
- Very large numbers (100000+)
- Decimal results
- Division by zero (error case)

Error Scenarios:
- Non-numeric input
- Missing parameters
- Invalid operator
```

**Scoring:**
- 1.0 (pass) or 0.0 (fail)
- No partial credit for exact match

**Example Eval Set:**

```json
{
  "version": "1.0",
  "id": "calculator-comprehensive",
  "name": "Calculator Comprehensive Tests",
  "evaluatorRefs": ["ExactMatchEvaluator"],
  "evaluations": [
    {
      "id": "test-1-add",
      "name": "Basic addition",
      "inputs": {"a": 5, "b": 3},
      "evaluationCriterias": {
        "ExactMatchEvaluator": {
          "expectedOutput": {"result": "8"}
        }
      }
    },
    {
      "id": "test-2-divide-by-zero",
      "name": "Error handling",
      "inputs": {"a": 10, "b": 0},
      "evaluationCriterias": {
        "ExactMatchEvaluator": {
          "expectedOutput": {"error": "Division by zero"}
        }
      }
    }
  ]
}
```

### Pattern 2: Natural Language Agents

For agents that generate text, summaries, or natural language output:

**Test Organization:**
```
eval-sets/
├── nlp-agent-semantics.json         # Semantic correctness
├── nlp-agent-keyword-checks.json    # Required keywords
└── nlp-agent-length-constraints.json # Output size limits
```

**Evaluator Selection:**
- **Primary:** LLMJudgeOutputEvaluator (semantic matching)
- **Secondary:** ContainsEvaluator (keyword checks)
- **Tertiary:** (optional) JsonSimilarityEvaluator for structured outputs

**Test Cases:**
```
Semantic Equivalence:
- Different phrasings of same concept
- Variations in word order
- Synonymous expressions

Keyword Validation:
- Must contain specific terms
- Must mention key concepts
- Should include certain information

Format Validation:
- Output length constraints
- Specific JSON structure
- Required fields present
```

**Scoring:**
- 0.0-1.0 range based on semantic similarity
- Accept 0.7+ for good semantic match

**Example Eval Set:**

```json
{
  "version": "1.0",
  "id": "summarizer-nlp",
  "name": "Document Summarizer NLP Tests",
  "evaluatorRefs": [
    "LLMJudgeOutputEvaluator",
    "ContainsEvaluator"
  ],
  "evaluations": [
    {
      "id": "test-1-semantic-match",
      "name": "Semantic equivalence test",
      "inputs": {
        "text": "The quick brown fox jumps over the lazy dog"
      },
      "evaluationCriterias": {
        "LLMJudgeOutputEvaluator": {
          "expectedOutput": {
            "summary": "A brief description mentioning a fox and jumping motion"
          }
        }
      }
    },
    {
      "id": "test-2-keywords",
      "name": "Verify key concepts present",
      "inputs": {
        "text": "Machine learning is a subset of artificial intelligence"
      },
      "evaluationCriterias": {
        "ContainsEvaluator": {
          "searchText": "machine learning"
        }
      }
    }
  ]
}
```

### Pattern 3: Multi-Step Orchestration Agents

For agents that coordinate multiple tools or services:

**Test Organization:**
```
eval-sets/
├── orchestrator-happy-path.json     # Normal workflows
├── orchestrator-tool-sequences.json # Specific execution paths
└── orchestrator-error-handling.json # Fallback paths
```

**Evaluator Selection:**
- **Primary:** TrajectoryEvaluator (execution path validation)
- **Secondary:** JsonSimilarityEvaluator (output structure)
- **Tertiary:** (optional) LLMJudgeOutputEvaluator (semantic check)

**Test Cases:**
```
Tool Sequence Validation:
- Tools called in expected order
- Correct tool chosen for each step
- Arguments passed correctly

Tool Interaction:
- Output of one tool becomes input to next
- Data flows correctly through pipeline
- State maintained between steps

Error Handling:
- Fallback paths when tool fails
- Graceful degradation
- Error reporting
```

**Scoring:**
- Trajectory: 0.0-1.0 based on execution path match
- Output: 0.0-1.0 based on structure match
- Average across evaluators

**Example Eval Set:**

```json
{
  "version": "1.0",
  "id": "orchestrator-workflow",
  "name": "Orchestrator Workflow Tests",
  "evaluatorRefs": [
    "TrajectoryEvaluator",
    "JsonSimilarityEvaluator"
  ],
  "evaluations": [
    {
      "id": "test-1-pipeline",
      "name": "Data pipeline execution",
      "inputs": {
        "dataSource": "database",
        "operation": "transform"
      },
      "evaluationCriterias": {
        "TrajectoryEvaluator": {
          "expectedAgentBehavior": "Agent should call fetch_data, then transform_data, then save_results in that order"
        },
        "JsonSimilarityEvaluator": {
          "expectedOutput": {
            "status": "complete",
            "recordsProcessed": 1000,
            "transformedData": {}
          }
        }
      }
    }
  ]
}
```

### Pattern 4: API Integration Agents

For agents that interact with external APIs:

**Test Organization:**
```
eval-sets/
├── api-agent-success-paths.json     # Successful API responses
├── api-agent-error-responses.json   # API errors
└── api-agent-retry-logic.json       # Retry mechanisms
```

**Evaluator Selection:**
- **Primary:** JsonSimilarityEvaluator (response structure)
- **Secondary:** ExactMatchEvaluator (specific fields)
- **Tertiary:** (optional) TrajectoryEvaluator (request patterns)

**Mocking Strategy:**
- Mock all external API calls
- Use function mocking (mockito type)
- Simulate various response types

**Test Cases:**
```
Success Paths:
- Valid API responses
- Different response formats
- Pagination handling

Error Handling:
- API errors (500, 404, 403)
- Timeout handling
- Malformed responses

Edge Cases:
- Empty results
- Large responses
- Rate limiting
```

**Example Eval Set:**

```json
{
  "version": "1.0",
  "id": "api-agent-integration",
  "name": "API Integration Tests",
  "evaluatorRefs": ["JsonSimilarityEvaluator"],
  "evaluations": [
    {
      "id": "test-1-fetch-user",
      "name": "Fetch user from API",
      "inputs": {"userId": "123"},
      "evaluationCriterias": {
        "JsonSimilarityEvaluator": {
          "expectedOutput": {
            "id": "123",
            "name": "John Doe",
            "email": "john@example.com"
          }
        }
      },
      "mockingStrategy": {
        "type": "mockito",
        "behaviors": [
          {
            "function": "api_call",
            "arguments": {
              "args": ["https://api.example.com/users/123"],
              "kwargs": {}
            },
            "then": [
              {
                "type": "return",
                "value": {
                  "id": "123",
                  "name": "John Doe",
                  "email": "john@example.com"
                }
              }
            ]
          }
        ]
      }
    },
    {
      "id": "test-2-api-error",
      "name": "Handle API error",
      "inputs": {"userId": "invalid"},
      "evaluationCriterias": {
        "JsonSimilarityEvaluator": {
          "expectedOutput": {
            "error": "User not found"
          }
        }
      },
      "mockingStrategy": {
        "type": "mockito",
        "behaviors": [
          {
            "function": "api_call",
            "arguments": {
              "args": ["https://api.example.com/users/invalid"],
              "kwargs": {}
            },
            "then": [
              {
                "type": "raise",
                "value": {
                  "_target_": "Exception",
                  "args": ["404 Not Found"]
                }
              }
            ]
          }
        ]
      }
    }
  ]
}
```

## Test Case Organization Tips

### By Scenario Type

```
eval-sets/
├── {agent}-happy-path.json
├── {agent}-edge-cases.json
├── {agent}-error-handling.json
└── {agent}-performance.json
```

### By Feature

```
eval-sets/
├── {agent}-feature-a.json
├── {agent}-feature-b.json
└── {agent}-feature-c.json
```

### By Evaluator Type

```
eval-sets/
├── {agent}-exact-match.json
├── {agent}-semantic.json
└── {agent}-trajectory.json
```

## Performance Optimization

### Test Execution

- **Use appropriate worker count**
  - 4 workers: good default
  - 8 workers: large evaluation sets
  - 1 worker: debugging failures

- **Enable caching for LLM evaluators**
  ```bash
  uv run uipath eval <agent> <eval-file> --mocker-cache
  ```
  - Faster re-runs
  - Lower API costs
  - Reproducible results

- **Run subset during development**
  - Create separate "smoke test" eval sets
  - Use for quick validation
  - Run full suite before committing

### Test Design

- **Minimize external dependencies**
  - Mock external API calls
  - Avoid real database calls
  - Use test data, not production data

- **Balance coverage vs. execution time**
  - Comprehensive test suite
  - But not so large it's slow
  - Run full suite in CI, smoke tests locally

- **Prioritize critical paths**
  - Test most important workflows first
  - Test happy path thoroughly
  - Add edge cases incrementally

## Maintenance

### Keeping Tests Current

- **Update when agent changes**
  - Agent input/output schema changes
  - New features added
  - Bug fixes require test updates

- **Review regularly**
  - Remove obsolete tests
  - Update test data
  - Refactor for clarity

- **Version evaluation sets**
  - Track changes over time
  - Maintain backward compatibility
  - Document breaking changes

### CI/CD Integration

- **Run evaluations in CI/CD**
  ```bash
  uv run uipath eval <agent> evaluations/eval-sets/smoke-tests.json \
    --workers 4 \
    --mocker-cache \
    --output-file eval-results.json
  ```

- **Fail pipeline on test failures**
  - Set clear pass/fail criteria
  - Monitor score trends
  - Alert on regressions

## Quick Reference

### Evaluation Set Template

```json
{
  "version": "1.0",
  "id": "my-eval-set",
  "name": "My Evaluation Set",
  "description": "Description of test scenarios",
  "evaluatorRefs": ["EvaluatorId"],
  "evaluations": [
    {
      "id": "test-1",
      "name": "Test name",
      "inputs": {},
      "evaluationCriterias": {
        "EvaluatorId": {}
      }
    }
  ]
}
```

### Evaluator Selection Quick Guide

| Agent Type | Primary Evaluator | Secondary | Notes |
|-----------|------------------|-----------|-------|
| Calculator | ExactMatch | - | Deterministic |
| Text Generator | LLMJudge | Contains | Natural language |
| Orchestrator | Trajectory | JsonSimilarity | Multi-step flow |
| API Client | JsonSimilarity | ExactMatch | Structured data |
| Summarizer | LLMJudge | Contains | Semantic matching |

## Next Steps

- [Creating Evaluations](creating-evaluations.md) - Start building tests
- [Evaluation Sets](evaluation-sets.md) - Structure your test files
- [Running Evaluations](running-evaluations.md) - Execute and analyze results
- [Evaluators Guide](evaluators/README.md) - Deep dive into evaluator types
