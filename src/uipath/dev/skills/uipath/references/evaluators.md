# Use Evaluators

Evaluators are the core components that validate agent output and execution. This guide provides detailed information on all available evaluator types and how to create custom evaluators.

## Quick Navigation

### Output-Based Evaluators

Measure final results and validate what your agent returns:

- **[Exact Match Evaluator](output-based/exact-match.md)** - Verify exact string matching
- **[Contains Evaluator](output-based/contains.md)** - Check if output contains specific text
- **[JSON Similarity Evaluator](output-based/json-similarity.md)** - Compare JSON structure similarity
- **[LLM Judge Output Evaluator](output-based/llm-judge-output.md)** - LLM-powered semantic assessment

See [Output-Based Overview](output-based/index.md) for comparison and selection guidance.

### Trajectory-Based Evaluators

Examine execution patterns and decision sequences during agent execution:

- **[LLM Judge Trajectory Evaluator](trajectory-based/trajectory.md)** - Validate execution paths and decision-making
- **[Tool Call Evaluators](trajectory-based/tool-calls.md)** - Validate tool sequences, counts, arguments, and outputs

See [Trajectory-Based Overview](trajectory-based/index.md) for detailed information.

### Custom Evaluators

When built-in evaluators don't meet your needs:

- **[Custom Python Evaluators](custom.md)** - Implement domain-specific evaluation logic

## Evaluator Selection Guide

| Agent Type | Recommended Evaluators | Why |
|-----------|----------------------|-----|
| Calculator/Deterministic | Exact Match | Deterministic results need exact match |
| Natural Language | LLM Judge Output, Contains | Semantic equivalence and keyword checks |
| Multi-Step Orchestration | Trajectory, JSON Similarity | Validate execution flow and output structure |
| API Integration | JSON Similarity, Exact Match | Flexible JSON matching with strict field validation |
| Multi-Tool Workflows | Tool Call Order/Count, Trajectory | Validate tool sequences and usage patterns |

## Evaluation Scoring

All evaluators return numeric scores:

- **1.0** - Perfect pass
- **0.5-0.9** - Partial success (for similarity-based evaluators)
- **0.0** - Complete failure

Results also include:
- **Justification** - Why the score was given
- **Execution metrics** - Performance data
- **Complete traces** - Full execution history for debugging

## Best Practices

✅ **Do:**
- Use multiple evaluators for comprehensive validation
- Mix output-based and trajectory-based evaluators for complex agents
- Create separate eval sets for different scenarios (happy path, edge cases, errors)
- Use trajectory evaluators for agents with multiple steps/tools
- Use LLM evaluators for natural language or fuzzy matching scenarios
- Start with exact match for deterministic outputs, then add LLM evaluators

❌ **Don't:**
- Use only exact match for natural language outputs
- Forget to test edge cases and error scenarios
- Use trajectory evaluators when output-based is sufficient
- Set too strict criteria early in development
- Skip schema validation during test creation

## Next Steps

- **Getting Started?** Start with [Output-Based Overview](output-based/index.md)
- **Complex Workflows?** Check [Trajectory-Based Overview](trajectory-based/index.md)
- **Domain-Specific Logic?** See [Custom Evaluators](custom.md)
- **Running Tests?** Go to [Running Evaluations](../running-evaluations.md)


---

# Custom Evaluators

Custom Python Evaluators enable you to implement domain-specific evaluation logic tailored to your agent's unique requirements. When the built-in evaluators don't cover your specific use case, you can create custom evaluators with full control over evaluation criteria and scoring logic.

## Overview

**Use Cases:**
- Domain-specific validation (healthcare data compliance, financial calculations)
- Complex multi-step verification logic
- Custom data extraction and comparison from tool calls
- Specialized scoring algorithms (Jaccard similarity, Levenshtein distance, etc.)
- Integration with external validation systems

**Returns:** Any `EvaluationResult` type (`NumericEvaluationResult`, `BooleanEvaluationResult`, or `ErrorEvaluationResult`)

## Project Structure

Custom evaluators must follow this directory structure:

```
your-project/
├── evals/
│   ├── evaluators/
│   │   ├── custom/
│   │   │   ├── your_evaluator.py       # Custom evaluator implementation
│   │   │   ├── another_evaluator.py    # Additional custom evaluators
│   │   │   └── types/                  # Auto-generated type schemas
│   │   │       ├── your-evaluator-types.json
│   │   │       └── another-evaluator-types.json
│   │   ├── your-evaluator.json         # Auto-generated config
│   │   └── another-evaluator.json
│   └── eval_sets/
│       └── your_eval_set.json
└── ...
```

**Important:** Custom evaluator files **must** be in `evals/evaluators/custom/` directory.

## Creating a Custom Evaluator

### Step 1: Generate Template

```bash
uipath add evaluator my-custom-evaluator
```

Creates `evals/evaluators/custom/my_custom_evaluator.py` with template structure.

### Step 2: Implement Evaluation Logic

A custom evaluator consists of three main components:

#### 1. Evaluation Criteria Class

Define the criteria specific to your evaluation:

```python
from pydantic import Field
from uipath.eval.evaluators import BaseEvaluationCriteria

class MyEvaluationCriteria(BaseEvaluationCriteria):
    """Criteria for my custom evaluator."""
    expected_values: list[str] = Field(default_factory=list)
```

#### 2. Evaluator Configuration Class

Define configuration options for your evaluator:

```python
from uipath.eval.evaluators import BaseEvaluatorConfig

class MyEvaluatorConfig(BaseEvaluatorConfig[MyEvaluationCriteria]):
    """Configuration for my custom evaluator."""
    name: str = "MyCustomEvaluator"
    threshold: float = 0.8  # Minimum score to consider passing
    case_sensitive: bool = False
```

#### 3. Evaluator Implementation Class

Implement the core evaluation logic:

```python
from uipath.eval.evaluators import BaseEvaluator
from uipath.eval.models import AgentExecution, NumericEvaluationResult

class MyCustomEvaluator(
    BaseEvaluator[MyEvaluationCriteria, MyEvaluatorConfig, str]
):
    """Custom evaluator with domain-specific logic."""

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: MyEvaluationCriteria
    ) -> NumericEvaluationResult:
        """Evaluate the agent execution against criteria."""
        # Extract data
        actual_values = self._extract_values(agent_execution)
        expected_values = evaluation_criteria.expected_values

        # Compute score
        score = self._compute_similarity(actual_values, expected_values)

        return NumericEvaluationResult(
            score=score,
            details=f"Expected: {expected_values}, Actual: {actual_values}"
        )

    def _extract_values(self, agent_execution: AgentExecution) -> list[str]:
        """Extract values from agent execution."""
        # Your custom extraction logic
        return []

    def _compute_similarity(self, actual: list[str], expected: list[str]) -> float:
        """Compute similarity score."""
        # Your custom scoring logic
        return 0.0

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the unique evaluator identifier."""
        return "MyCustomEvaluator"
```

### Step 3: Register the Evaluator

```bash
uipath register evaluator my_custom_evaluator.py
```

This command:
1. Validates your evaluator implementation
2. Generates `evals/evaluators/custom/types/my-custom-evaluator-types.json`
3. Creates `evals/evaluators/my-custom-evaluator.json`

The generated configuration:

```json
{
  "version": "1.0",
  "id": "MyCustomEvaluator",
  "evaluatorTypeId": "file://types/my-custom-evaluator-types.json",
  "evaluatorSchema": "file://my_custom_evaluator.py:MyCustomEvaluator",
  "description": "Custom evaluator with domain-specific logic...",
  "evaluatorConfig": {
    "name": "MyCustomEvaluator",
    "threshold": 0.8,
    "caseSensitive": false
  }
}
```

### Step 4: Use in Evaluation Sets

Reference your custom evaluator in evaluation sets:

```json
{
  "version": "1.0",
  "id": "my-eval-set",
  "evaluatorRefs": ["MyCustomEvaluator"],
  "evaluationItems": [
    {
      "id": "test-1",
      "agentInput": {"query": "Process data"},
      "evaluations": [
        {
          "evaluatorId": "MyCustomEvaluator",
          "evaluationCriteria": {
            "expectedValues": ["value1", "value2"]
          }
        }
      ]
    }
  ]
}
```

## Working with Agent Traces

Custom evaluators often extract information from tool calls in the agent execution trace.

### Extracting Tool Calls

```python
from uipath.eval._helpers.evaluators_helpers import extract_tool_calls

def _process_tool_calls(self, agent_execution: AgentExecution) -> list[str]:
    """Extract and process tool calls from the execution trace."""
    tool_calls = extract_tool_calls(agent_execution.agent_trace)

    results = []
    for tool_call in tool_calls:
        tool_name = tool_call.name
        args = tool_call.args or {}

        if tool_name == "SpecificTool":
            data = args.get("parameter_name", "")
            results.append(data)

    return results
```

### Available Helper Functions

```python
from uipath.eval._helpers.evaluators_helpers import (
    extract_tool_calls,          # Extract tool calls with arguments
    extract_tool_calls_names,     # Extract just tool names
    extract_tool_calls_outputs,   # Extract tool outputs
    trace_to_str,                 # Convert trace to string
)
```

## Best Practices

### 1. Type Annotations and Documentation

```python
def _extract_data(
    self,
    agent_execution: AgentExecution,
    tool_name: str
) -> list[str]:
    """Extract data from specific tool calls.

    Args:
        agent_execution: The agent execution to process
        tool_name: The name of the tool to extract data from

    Returns:
        List of extracted data strings

    Raises:
        ValueError: If the tool call format is invalid
    """
```

### 2. Error Handling

```python
from uipath.eval.models import ErrorEvaluationResult

async def evaluate(
    self,
    agent_execution: AgentExecution,
    evaluation_criteria: MyCriteria
) -> EvaluationResult:
    """Evaluate with error handling."""
    try:
        score = self._compute_score(agent_execution)
        return NumericEvaluationResult(score=score)
    except Exception as e:
        return ErrorEvaluationResult(
            error=f"Evaluation failed: {str(e)}"
        )
```

### 3. Clear Scoring Logic

```python
def _compute_score(
    self,
    actual: list[str],
    expected: list[str]
) -> float:
    """Compute evaluation score.

    Scoring algorithm:
    - 1.0: Perfect match (all expected items found)
    - 0.5-0.99: Partial match (some items found)
    - 0.0: No match (no items found)
    """
    if not expected:
        return 1.0 if not actual else 0.0

    matches = len(set(actual).intersection(set(expected)))
    return matches / len(expected)
```

### 4. Testing

```python
import pytest
from uipath.eval.models import AgentExecution

@pytest.mark.asyncio
async def test_custom_evaluator() -> None:
    """Test custom evaluator logic."""
    agent_execution = AgentExecution(
        agent_input={"query": "test"},
        agent_output={"result": "test output"},
        agent_trace=[],
    )

    evaluator = MyCustomEvaluator(
        id="test-evaluator",
        config={
            "name": "MyCustomEvaluator",
            "threshold": 0.8,
        }
    )

    criteria = MyEvaluationCriteria(expected_values=["value1"])
    result = await evaluator.evaluate(agent_execution, criteria)

    assert result.score >= 0.0
    assert result.score <= 1.0
```

## Common Patterns

### Pattern 1: Extract Data from Specific Tools

```python
def _extract_from_specific_tool(
    self, agent_execution: AgentExecution
) -> str:
    """Extract data from a specific tool call."""
    tool_calls = extract_tool_calls(agent_execution.agent_trace)

    for tool_call in tool_calls:
        if tool_call.name == "TargetTool":
            args = tool_call.args or {}
            return str(args.get("target_parameter", ""))

    return ""
```

### Pattern 2: Set-Based Similarity

```python
def _compute_set_similarity(
    self, actual: list[str], expected: list[str]
) -> float:
    """Compute similarity using set operations (Jaccard similarity)."""
    expected_set = set(expected) if expected else set()
    actual_set = set(actual) if actual else set()

    if len(expected_set) == 0 and len(actual_set) == 0:
        return 1.0

    intersection = len(expected_set.intersection(actual_set))
    union = len(expected_set.union(actual_set))
    return intersection / union if union > 0 else 0.0
```

## Troubleshooting

### Evaluator Not Found

**Error:** `Could not find '<filename>' in evals/evaluators/custom folder`

**Solution:** Ensure file is in `evals/evaluators/custom/` directory.

### Class Not Inheriting from BaseEvaluator

**Error:** `Could not find a class inheriting from BaseEvaluator`

**Solution:** Verify class properly inherits:

```python
from uipath.eval.evaluators import BaseEvaluator

class MyEvaluator(BaseEvaluator[...]):  # ✓ Correct
    pass
```

### Missing get_evaluator_id Method

**Error:** `Error getting evaluator ID`

**Solution:** Implement required class method:

```python
@classmethod
def get_evaluator_id(cls) -> str:
    return "MyUniqueEvaluatorId"
```

## Generic Type Parameters

```python
class MyEvaluator(BaseEvaluator[T, C, J]):
    """
    T: Evaluation criteria type (subclass of BaseEvaluationCriteria)
    C: Configuration type (subclass of BaseEvaluatorConfig[T])
    J: Justification type (str, None, or BaseEvaluatorJustification)
    """
```

## Related Documentation

- [Output-Based Evaluators](output-based/index.md): Built-in output evaluators
- [Trajectory-Based Evaluators](trajectory-based/index.md): Built-in trajectory evaluators
- [Running Evaluations](../running-evaluations.md): How to execute evaluations
- [Evaluation Sets](../evaluation-sets.md): Defining test cases

## Next Steps

- [Back to Evaluators Overview](README.md)
- [Running Evaluations](../running-evaluations.md)
- [Best Practices](../best-practices.md)


---

# Contains Evaluator

Checks whether the agent's output contains a specific search text (substring matching).

## Overview

**Evaluator ID:** `contains`

**Use Cases:**
- Verify specific keywords or phrases appear in output
- Check for presence of expected content
- Test that error messages contain specific text
- Validate outputs include required information

**Returns:** Binary score (1.0 if found, 0.0 if not found)

## Configuration

### Key Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"ContainsEvaluator"` | Display name |
| `case_sensitive` | `bool` | `False` | Case-sensitive search |
| `negated` | `bool` | `False` | If True, passes when text is NOT found |
| `target_output_key` | `str` | `"*"` | Specific field to search (use "*" for entire output) |
| `default_evaluation_criteria` | `dict` | `None` | Default criteria if not specified per test |

**Important:** Agent output must be a dictionary. The value is converted to a string before checking.

## Evaluation Criteria

```json
{
  "search_text": "text-to-search-for"
}
```

## Scoring

- **1.0** - Search text found in output
- **0.0** - Search text not found

## Usage Examples

### Basic Keyword Search

```json
{
  "version": "1.0",
  "id": "ContainsEvaluator",
  "description": "Validates keyword presence",
  "evaluatorTypeId": "uipath-contains",
  "evaluatorConfig": {
    "name": "ContainsEvaluator",
    "case_sensitive": false,
    "targetOutputKey": "response"
  }
}
```

In test: Search for `"Paris"` in response `"The capital of France is Paris."` → **Score: 1.0**

### Case-Sensitive Search

```json
{
  "evaluatorConfig": {
    "name": "ContainsEvaluator",
    "case_sensitive": true,
    "targetOutputKey": "message"
  }
}
```

Search for `"hello"` in `"Hello World"` with case-sensitive=true → **Score: 0.0** (case mismatch)

### Negated Search

Pass when text is NOT present:

```json
{
  "evaluatorConfig": {
    "name": "ContainsEvaluator",
    "negated": true,
    "targetOutputKey": "status"
  }
}
```

Search for `"error"` in `"Success: Operation completed"` with negated=true → **Score: 1.0** (error not found, which is what we want)

### Target Specific Field

Only search within one field:

```json
{
  "evaluatorConfig": {
    "name": "ContainsEvaluator",
    "targetOutputKey": "message"
  }
}
```

Agent output:
```json
{
  "status": "success",
  "message": "User profile updated successfully"
}
```

Search for `"updated"` → Only searches in "message" field → **Score: 1.0**

## Best Practices

1. **Use case-insensitive matching** by default to make tests more robust
2. **Combine with other evaluators** for comprehensive validation
3. **Use negated mode** to ensure error messages or sensitive data are NOT present
4. **Target specific fields** when evaluating structured outputs to reduce false positives
5. **Remember substring matching** - this evaluator uses substring search, not full-text or regex

## Common Use Cases

### Validate Required Keywords

Multiple evaluators for different keywords:

```json
{
  "evaluations": [
    {
      "evaluatorId": "contains-greeting",
      "evaluationCriteria": {"search_text": "hello"}
    },
    {
      "evaluatorId": "contains-name",
      "evaluationCriteria": {"search_text": "John"}
    }
  ]
}
```

### Ensure No Error Messages

Use negated mode:

```json
{
  "evaluatorId": "no-errors",
  "evaluationCriteria": {"search_text": "error"},
  "config": {"negated": true}
}
```

### Email Validation

Check email contains required domain:

```json
{
  "evaluatorId": "email-domain",
  "evaluationCriteria": {"search_text": "@company.com"},
  "config": {"targetOutputKey": "email"}
}
```

## When to Use

✅ Use Contains when:
- Specific keywords must be present
- Partial text matching is sufficient
- Flexible text variations acceptable
- Checking for required information in long responses

❌ Don't use when:
- Exact match required
- Complex pattern matching needed (use regex in custom evaluator)
- Entire JSON structure needs validation (use JSON Similarity)

## When NOT to Use

- For exact text matching (use [Exact Match Evaluator](exact-match.md))
- For complex pattern matching (use custom evaluator with regex)
- For natural language semantic matching (use [LLM Judge](llm-judge-output.md))
- For JSON structure validation (use [JSON Similarity](json-similarity.md))

## Related Evaluators

- [Exact Match Evaluator](exact-match.md): For exact string matching
- [JSON Similarity Evaluator](json-similarity.md): For structural comparison
- [LLM Judge Output Evaluator](llm-judge-output.md): For semantic similarity

## Next Steps

- [Back to Output-Based Overview](index.md)
- [JSON Similarity Evaluator](json-similarity.md)
- [Running Evaluations](../../running-evaluations.md)


---

# Exact Match Evaluator

Verifies exact string matching between agent output and expected output. This is the most strict deterministic evaluator.

## Overview

**Evaluator ID:** `exact-match`

**Use Cases:**
- Validate exact responses (status codes, IDs)
- Test deterministic outputs
- Ensure precise formatting is maintained
- Verify exact data values

**Returns:** Binary score (1.0 if exact match, 0.0 otherwise)

## Configuration

### Key Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"ExactMatchEvaluator"` | Display name |
| `case_sensitive` | `bool` | `False` | Case-sensitive comparison |
| `negated` | `bool` | `False` | If True, passes when outputs do NOT match |
| `target_output_key` | `str` | `"*"` | Specific field to evaluate (use "*" for entire output) |
| `default_evaluation_criteria` | `dict` | `None` | Default expected output if not specified per test |

**Important:** Agent output must always be a dictionary (e.g., `{"result": "value"}`). Use `target_output_key` to extract specific fields.

## Evaluation Criteria

```json
{
  "expected_output": {
    "result": "exact-value-here"
  }
}
```

## Scoring

- **1.0** - Exact match found
- **0.0** - No match

## Usage Examples

### Basic Exact Match

Compare the entire output as a dictionary:

```json
{
  "version": "1.0",
  "id": "ExactMatchEvaluator",
  "description": "Exact string matching validator",
  "evaluatorTypeId": "uipath-exact-match",
  "evaluatorConfig": {
    "name": "ExactMatchEvaluator",
    "targetOutputKey": "*",
    "case_sensitive": false,
    "negated": false,
    "defaultEvaluationCriteria": {
      "expectedOutput": {
        "status": "success",
        "code": 200
      }
    }
  }
}
```

### Case-Sensitive Matching

Fail on case mismatch:

```json
{
  "evaluatorConfig": {
    "name": "ExactMatchEvaluator",
    "case_sensitive": true,
    "targetOutputKey": "status"
  }
}
```

### Target Specific Field

Only compare one field from output:

```json
{
  "evaluatorConfig": {
    "name": "ExactMatchEvaluator",
    "targetOutputKey": "result"
  }
}
```

Agent output `{"result": "approved", "timestamp": "2024-01-01"}` with `expected_output: {"result": "approved"}` → **Score: 1.0** (timestamp ignored)

### Negated Mode

Pass when outputs do NOT match:

```json
{
  "evaluatorConfig": {
    "name": "ExactMatchEvaluator",
    "negated": true,
    "targetOutputKey": "error"
  }
}
```

Agent output `{"error": null}` vs expected `{"error": "validation error"}` → **Score: 1.0** (they don't match, which is what we want)

## Best Practices

1. **Use for deterministic outputs** where exact matches are expected
2. **Consider case sensitivity** - use insensitive mode by default for robustness
3. **Use case-insensitive mode** by default for more robust tests
4. **For structured data**, consider using [JSON Similarity Evaluator](json-similarity.md) instead
5. **Combine with other evaluators** for comprehensive testing
6. **Be careful with whitespace** - exact match includes all whitespace characters

## Common Issues

### Whitespace Sensitivity

Exact Match includes all whitespace:
- `"hello"` ≠ `"hello "` (trailing space)
- `"hello\nworld"` ≠ `"hello world"` (newline vs space)

**Solution:** Trim whitespace in your agent output or use JSON Similarity for tolerance.

### Case Sensitivity

By default, case-insensitive. Enable only if case matters:
```json
{
  "case_sensitive": true
}
```

### Type Mismatch

Expected `"5"` (string) but got `5` (number):
- Case-sensitive: Fails
- Use JSON Similarity if type flexibility needed

## When NOT to Use

- When output can vary slightly but still be correct
- For natural language outputs (use [LLM Judge](llm-judge-output.md) instead)
- When comparing complex JSON structures (use [JSON Similarity](json-similarity.md))
- When partial matches are acceptable (use [Contains](contains.md))

## Related Evaluators

- [Contains Evaluator](contains.md): For partial string matching
- [JSON Similarity Evaluator](json-similarity.md): For flexible JSON comparison
- [LLM Judge Output Evaluator](llm-judge-output.md): For semantic similarity

## Next Steps

- [Back to Output-Based Overview](index.md)
- [JSON Similarity Evaluator](json-similarity.md)
- [Running Evaluations](../../running-evaluations.md)


---

# JSON Similarity Evaluator

Performs flexible structural comparison of JSON-like outputs using a tree-based matching algorithm.

## Overview

**Evaluator ID:** `json-similarity`

**Use Cases:**
- Compare complex nested JSON structures
- Validate API responses with tolerance for minor differences
- Test structured outputs where exact matches are too strict
- Measure similarity when numeric values may vary slightly

**Returns:** Continuous score from 0.0 to 1.0 (0-100% similarity)

## How It Works

### Tree-Based Matching Algorithm

1. **Tree Structure:** Treats JSON/dictionary as tree with nested objects and arrays
2. **Leaf Comparison:** Only leaf nodes (actual values) are compared using type-specific similarity:
   - **Strings:** Levenshtein distance (edit distance) for textual similarity
   - **Numbers:** Absolute difference with tolerance (within 1% considered similar)
   - **Booleans:** Exact match required (binary comparison)
3. **Structural Recursion:** Recursively traverses and compares:
   - **Objects:** All expected keys (extra keys in actual output ignored)
   - **Arrays:** Elements by position (index-based matching)
4. **Score Calculation:** `matched_leaves / total_leaves`

The final score represents the percentage of matching leaf nodes in the tree structure.

## Configuration

### Key Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"JsonSimilarityEvaluator"` | Display name |
| `target_output_key` | `str` | `"*"` | Specific field to evaluate (use "*" for entire output) |
| `default_evaluation_criteria` | `dict` | `None` | Default expected structure |

## Evaluation Criteria

```json
{
  "expected_output": {
    "field1": "value1",
    "nested": {
      "field2": "value2"
    }
  }
}
```

## Scoring

| Score Range | Interpretation |
|-------------|----------------|
| **1.0** | Perfect match (all leaves identical) |
| **0.9-0.99** | Very high similarity (minor differences) |
| **0.7-0.89** | Good similarity (some differences) |
| **0.5-0.69** | Moderate similarity (significant differences) |
| **0.0-0.49** | Low similarity (major differences) |

## Usage Examples

### Basic JSON Comparison

```json
{
  "version": "1.0",
  "id": "JsonSimilarityEvaluator",
  "evaluatorTypeId": "uipath-json-similarity",
  "evaluatorConfig": {
    "name": "JsonSimilarityEvaluator",
    "targetOutputKey": "*"
  }
}
```

Test:
- Input: `{"name": "John Doe", "age": 30, "city": "New York"}`
- Expected: `{"name": "John Doe", "age": 30, "city": "New York"}`
- **Score: 1.0** (perfect match, 3/3 leaves matched)

### Numeric Tolerance

Numbers within ~1% are considered similar:

```json
{
  "temperature": 20.5,
  "humidity": 65
}
```

vs expected:

```json
{
  "temperature": 20.3,
  "humidity": 65
}
```

- Temperature: 20.5 vs 20.3 (0.2 difference, ~1%) → Similar
- Humidity: 65 vs 65 → Exact
- **Score: ~0.99** (very high similarity despite numeric difference)

### String Similarity

Typos don't cause complete failure (Levenshtein distance):

```json
{
  "status": "completed sucessfully"  // typo: "sucessfully" not "successfully"
}
```

vs expected:

```json
{
  "status": "completed successfully"
}
```

- String similarity calculated using edit distance
- **Score: ~0.95** (high similarity despite typo)

### Nested Structures

Recursively compares all levels:

```json
{
  "user": {
    "name": "Alice",
    "profile": {
      "age": 25,
      "location": "Paris"
    }
  },
  "status": "active"
}
```

All fields from different nesting levels are compared as leaf nodes.

### Array Comparison

Arrays compared by position (index-based):

```json
{
  "items": ["apple", "banana", "orange"]
}
```

vs expected:

```json
{
  "items": ["apple", "banana", "grape"]
}
```

- Position 0: "apple" = "apple" ✓
- Position 1: "banana" = "banana" ✓
- Position 2: "orange" ≠ "grape" ✗
- **Score: ~0.67** (2/3 correct)

### Handling Extra Keys

Extra keys in actual output are ignored:

```json
{
  "name": "Bob",
  "age": 30,
  "extra_field": "ignored"
}
```

vs expected:

```json
{
  "name": "Bob",
  "age": 30
}
```

Only expected keys evaluated → **Score: 1.0**

### Target Specific Field

Only compare one field from output:

```json
{
  "evaluatorConfig": {
    "name": "JsonSimilarityEvaluator",
    "targetOutputKey": "result"
  }
}
```

Agent output:
```json
{
  "result": {"score": 95, "passed": true},
  "metadata": {"timestamp": "2024-01-01"}
}
```

Only "result" field compared → metadata ignored.

## Best Practices

1. **Use for structured data** like JSON, dictionaries, or objects
2. **Set score thresholds** based on your tolerance (e.g., require score ≥ 0.9)
3. **Combine with exact match** for critical fields that must match exactly
4. **Only expected keys matter** - extra keys in actual output are automatically ignored
5. **Consider array order** - elements are compared by position
6. **Useful for API testing** where responses may have minor variations

## When to Use vs Other Evaluators

**Use JSON Similarity when:**
- Comparing complex nested structures
- Minor numeric differences are acceptable
- String typos shouldn't cause complete failure
- You need a granular similarity score
- API responses may have minor variations

**Use Exact Match when:**
- Output must match precisely
- No tolerance for any differences
- Simple string comparison needed

**Use LLM Judge when:**
- Semantic meaning matters more than structure
- Natural language comparison needed
- Context and intent should be considered

## Common Issues

### Array Order Matters

If order shouldn't matter, use custom evaluator with set-based comparison instead.

### Missing Fields

If actual output lacks expected field, it scores lower than with all fields present.

### Type Mismatch

`5` (number) vs `"5"` (string) are compared differently:
- Numbers use numeric tolerance
- Strings use Levenshtein distance
- Result: Different similarity scores

### Floating Point Precision

Numbers with floating point differences:
- `3.14159` vs `3.14160` → Very high similarity (within 1%)

## Performance

- **Speed:** Fast (no LLM calls, pure algorithmic)
- **Complexity:** O(n) where n = total number of leaf nodes
- **Memory:** Efficient (doesn't require full tree materialization)

## Related Evaluators

- [Exact Match Evaluator](exact-match.md): For strict matching
- [Contains Evaluator](contains.md): For substring matching
- [LLM Judge Output Evaluator](llm-judge-output.md): For semantic comparison

## Next Steps

- [Back to Output-Based Overview](index.md)
- [LLM Judge Evaluator](llm-judge-output.md)
- [Running Evaluations](../../running-evaluations.md)


---

# LLM Judge Output Evaluators

Uses Language Models to assess the quality and semantic similarity of agent outputs. These evaluators are ideal when deterministic comparison is insufficient and human-like judgment is needed.

## Overview

There are two variants:

1. **LLM Judge Output Evaluator** - General semantic similarity evaluation
2. **LLM Judge Strict JSON Similarity Output Evaluator** - Strict JSON structure matching with LLM judgment

**Use Cases:**
- Evaluate natural language outputs
- Assess semantic similarity beyond exact matching
- Judge output quality based on intent and meaning
- Validate structured outputs with flexible criteria

**Returns:** Continuous score from 0.0 to 1.0 with LLM justification

## LLM Service Integration

LLM Judge evaluators use the **UiPathLlmService** by default, which:
- Integrates with configured LLM providers through the UiPath platform
- Supports multiple providers (OpenAI, Anthropic, etc.)
- Allows custom LLM service if needed

### Model Selection

Specify the model according to your LLM service's conventions:

```json
{
  "model": "gpt-4o-2024-11-20",  // OpenAI
  "model": "claude-3-5-sonnet-20241022"  // Anthropic
}
```

## LLM Judge Output Evaluator

### Overview

**Evaluator ID:** `llm-judge-output-semantic-similarity`

General semantic similarity evaluation using LLM judgment.

### Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"LLMJudgeOutputEvaluator"` | Display name |
| `model` | `str` | Required | LLM model to use |
| `temperature` | `float` | `0.0` | LLM temperature (0.0 for deterministic) |
| `max_tokens` | `int` | `None` | Maximum tokens for response |
| `prompt` | `str` | Default | Custom evaluation prompt |
| `target_output_key` | `str` | `"*"` | Specific field to evaluate |
| `default_evaluation_criteria` | `dict` | `None` | Default criteria |

### Evaluation Criteria

```json
{
  "expected_output": {
    "result": "Expected text or description"
  }
}
```

### Prompt Placeholders

The prompt template supports these placeholders:

- `{{ActualOutput}}` - The output produced by the agent
- `{{ExpectedOutput}}` - The expected output from criteria

### Usage Examples

#### Basic Semantic Similarity

```json
{
  "version": "1.0",
  "id": "LLMJudgeOutputEvaluator",
  "evaluatorTypeId": "uipath-llm-judge-output-semantic-similarity",
  "evaluatorConfig": {
    "name": "LLMJudgeOutputEvaluator",
    "model": "gpt-4o-2024-11-20",
    "temperature": 0.0,
    "targetOutputKey": "answer"
  }
}
```

Test:
- Input: `{"query": "What is the capital of France?"}`
- Actual output: `{"answer": "Paris is the capital city of France."}`
- Expected: `{"answer": "The capital of France is Paris."}`
- **Score: ~0.95** (semantically equivalent, different wording)

#### Custom Evaluation Prompt

```json
{
  "evaluatorConfig": {
    "name": "LLMJudgeOutputEvaluator",
    "model": "gpt-4o-2024-11-20",
    "temperature": 0.0,
    "prompt": "Compare the actual output with the expected output.\nFocus on semantic meaning and intent rather than exact wording.\n\nActual Output: {{ActualOutput}}\nExpected Output: {{ExpectedOutput}}\n\nProvide a score from 0-100 based on semantic similarity."
  }
}
```

#### Natural Language Quality Assessment

Evaluate email quality:
- Actual: Multi-sentence professional response
- Expected: Professional, courteous response addressing the inquiry
- **Score: 0.9-0.95** (LLM judges professionalism and tone)

### Best Practices

1. **Use temperature 0.0** for deterministic evaluations
2. **Craft clear prompts** - Be specific about evaluation criteria
3. **Include both placeholders** - Always use `{{ActualOutput}}` and `{{ExpectedOutput}}`
4. **Set score thresholds** - Define minimum acceptable scores (e.g., ≥ 0.8)
5. **Review justifications** - Use LLM explanations to understand scores
6. **Cost awareness** - LLM evaluations use API calls, monitor token costs

## LLM Judge Strict JSON Similarity Output Evaluator

### Overview

**Evaluator ID:** `llm-judge-output-strict-json-similarity`

Performs **per-key matching** on JSON structures with penalty-based scoring.

### How It Works

1. **Key Inventory:** Identifies all top-level keys in expected and actual outputs
2. **Per-Key Matching:** For each expected key, checks if it exists in actual output
3. **Content Assessment:** For matching keys, evaluates content similarity (identical/similar/different)
4. **Penalty-Based Scoring:** Calculates score using penalties per key (where N = total expected keys):
   - **Missing key** (not in actual): `100/N` penalty
   - **Wrong key** (exists but different content): `100/N` penalty
   - **Similar key** (similar content): `50/N` penalty
   - **Identical key** (identical content): `0` penalty
   - **Extra key** (in actual but not expected): `10/N` penalty

**Final Score:** `100 - total_penalty` (normalized to 0-1 scale)

### Why "Strict"?

Unlike standard `LLMJudgeOutputEvaluator` which evaluates semantic similarity holistically:
- **Enforces structural matching** - Each expected key must be present
- **Penalizes missing keys heavily** - Same as wrong content (100/N penalty)
- **Evaluates per-key** - Independence between key evaluations
- **Deterministic scoring formula** - Mechanical calculation based on key-level assessments

### Configuration

Same as LLMJudgeOutputEvaluator

### Usage Example

```json
{
  "version": "1.0",
  "id": "LLMJudgeStrictJSONSimilarity",
  "evaluatorTypeId": "uipath-llm-judge-output-strict-json-similarity",
  "evaluatorConfig": {
    "name": "LLMJudgeStrictJSONSimilarityOutputEvaluator",
    "model": "gpt-4o-2024-11-20",
    "temperature": 0.0
  }
}
```

Test with 4 expected keys:
- Actual output has all 4 keys with similar/identical content
- **Score: 100 - penalties** based on per-key matching
- Example: 1 identical (0), 2 similar (50/4 + 50/4 = 25), 1 wrong (100/4 = 25) → Score: 50

## When to Use vs Other Evaluators

### Use LLM Judge Output when:
- Semantic meaning matters more than exact wording
- Natural language outputs need human-like judgment
- Context and intent are important
- Flexible evaluation criteria needed
- Cost is acceptable for improved accuracy

### Use Deterministic Evaluators when:
- Exact matches are required
- Output format is predictable
- Speed and cost are priorities
- No ambiguity in correctness

### Use Strict JSON when:
- JSON structure is critical
- Each key must be present
- Per-key evaluation needed
- Less flexible than standard LLM Judge

## Configuration Tips

### Temperature Settings

- **0.0** (recommended): Deterministic, consistent results
- **0.1**: Slight variation for nuanced judgment
- **>0.3**: Not recommended (too inconsistent for evaluation)

### Cost Considerations

- Each evaluation makes one LLM API call
- Token usage depends on:
  - Length of actual output
  - Length of expected output
  - Prompt length
- Consider caching for repeated evaluations

## Error Handling

The evaluator will raise `UiPathEvaluationError` if:
- LLM service is unavailable
- Prompt doesn't contain required placeholders
- LLM response cannot be parsed
- Model returns invalid JSON

## Related Evaluators

- [Exact Match Evaluator](exact-match.md): For strict string matching
- [JSON Similarity Evaluator](json-similarity.md): For deterministic JSON comparison
- [Contains Evaluator](contains.md): For substring matching
- [LLM Judge Trajectory Evaluator](../trajectory-based/trajectory.md): For evaluating execution paths

## Next Steps

- [Back to Output-Based Overview](index.md)
- [Running Evaluations](../../running-evaluations.md)
- [Best Practices](../../best-practices.md)


---

# LLM Judge Trajectory Evaluator

Uses Language Models to assess the quality of agent execution trajectories - the sequence of decisions and actions an agent takes.

## Overview

**Evaluator ID:** `llm-judge-trajectory-similarity`

**Use Cases:**
- Validate agent decision-making processes
- Ensure agents follow expected execution paths
- Evaluate tool usage patterns and sequencing
- Assess agent behavior in complex scenarios
- Validate multi-step workflows

**Returns:** Continuous score from 0.0 to 1.0 with justification

## Variants

Two variants available:

1. **LLM Judge Trajectory Evaluator** - General trajectory evaluation
2. **LLM Judge Trajectory Simulation Evaluator** - For tool simulation scenarios

## Configuration

### Key Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"LLMJudgeTrajectoryEvaluator"` | Display name |
| `model` | `str` | Required | LLM model to use |
| `temperature` | `float` | `0.0` | LLM temperature (0.0 for deterministic) |
| `max_tokens` | `int` | `None` | Maximum tokens for response |
| `prompt` | `str` | Default | Custom evaluation prompt |
| `default_evaluation_criteria` | `dict` | `None` | Default criteria |

## Evaluation Criteria

```json
{
  "expected_agent_behavior": "Detailed description of expected behavior"
}
```

## Prompt Placeholders

The prompt template supports these placeholders:

- `{{AgentRunHistory}}` - The agent's execution trace/trajectory
- `{{ExpectedAgentBehavior}}` - The expected behavior description
- `{{UserOrSyntheticInput}}` - The input provided to the agent

## Understanding Agent Traces

The agent execution trace contains spans showing:

- **Tool calls** made by the agent
- **LLM reasoning** steps
- **Decision points** and choices
- **Action sequences** in order
- **Intermediate results** between steps

Example trace structure:
```python
agent_trace = [
    {
        "name": "search_flights",
        "type": "tool",
        "inputs": {"destination": "Paris"},
        "output": {"flights": [...]}
    },
    {
        "name": "llm_reasoning",
        "type": "llm",
        "content": "User wants cheapest option..."
    },
    {
        "name": "book_flight",
        "type": "tool",
        "inputs": {"flight_id": "FL123"},
        "output": {"status": "confirmed"}
    }
]
```

## Usage Examples

### Basic Trajectory Evaluation

```json
{
  "version": "1.0",
  "id": "TrajectoryJudge",
  "evaluatorTypeId": "llm-judge-trajectory-similarity",
  "evaluatorConfig": {
    "name": "LLMJudgeTrajectoryEvaluator",
    "model": "gpt-4o-2024-11-20",
    "temperature": 0.0
  }
}
```

Test:
- Input: `{"user_query": "Book a flight to Paris"}`
- Expected behavior: `"Agent should search flights, present options, process booking, confirm"`
- Actual trace: Shows search → present → book → confirm sequence
- **Score: ~0.95** (followed expected sequence with good decision-making)

### Detailed Behavior Description

```json
{
  "expected_agent_behavior": """
  The agent should follow this sequence:

  1. Validate user authentication status
     - If not authenticated, request login
     - If authenticated, proceed to step 2

  2. Fetch user's order history
     - Use the get_orders tool with user_id

  3. Identify the problematic order
     - Search for orders with 'delayed' status

  4. Provide explanation to user
     - Include order details and delay reason

  5. Offer resolution
     - Present refund or expedited shipping options

  The agent should maintain a helpful tone throughout
  and adapt responses based on user reactions.
  """
}
```

### Custom Evaluation Prompt

```json
{
  "evaluatorConfig": {
    "name": "LLMJudgeTrajectoryEvaluator",
    "model": "gpt-4o-2024-11-20",
    "prompt": "Analyze the agent's execution path and compare it with the expected behavior.\n\nAgent Run History:\n{{AgentRunHistory}}\n\nExpected Agent Behavior:\n{{ExpectedAgentBehavior}}\n\nUser Input:\n{{UserOrSyntheticInput}}\n\nEvaluate:\n1. Did the agent follow the expected sequence?\n2. Were all necessary steps completed?\n3. Was the decision-making logical and efficient?\n\nProvide a score from 0-100."
  }
}
```

## Writing Good Behavior Descriptions

### Good Example (Specific and Clear)

```
The agent should:
1. First validate the user exists and is authenticated
   - If not authenticated, request login credentials
   - If not found, return error
2. Fetch the user's current order status from database
3. Compare actual status with 'shipped' status
4. If shipped, provide tracking number
5. If not shipped, provide estimated delivery date
6. Ask if user needs further assistance
```

### Poor Example (Vague and Ambiguous)

```
Help the user with their order problem
```

### Best Practices for Descriptions

**Include:**
1. Sequential steps (numbered or ordered list)
2. Decision points (when agent should make choices)
3. Conditional logic ("If X, then Y" scenarios)
4. Success criteria (what constitutes good behavior)
5. Error handling expectations

**Be specific about:**
- Tool names that should be called
- Data that should be extracted
- Decisions to make at key points
- Order and sequencing

## LLM Judge Trajectory Simulation Evaluator

### Overview

**Evaluator ID:** `llm-judge-trajectory-simulation`

Specialized variant for evaluating agent behavior in **tool simulation scenarios**, where tool responses are mocked.

### What is Tool Simulation?

In tool simulation:
1. **Simulation Engine:** Mocks tool responses based on simulation instructions
2. **Agent Unawareness:** Agent doesn't know responses are simulated
3. **Controlled Testing:** Test agent behavior with predictable tool responses
4. **Evaluation Focus:** Assess if agent behaves correctly given simulated responses

### How It Differs

The evaluator checks:
- Simulation was successful (tools responded as instructed)
- Agent behaved according to expectations given simulated responses
- Agent's decision-making aligns with expected behavior in simulated scenario

### Configuration

Same as standard LLM Judge Trajectory Evaluator

### Additional Prompt Placeholder

- `{{SimulationInstructions}}` - Tool simulation instructions specifying expected tool responses

### Usage Example

```json
{
  "evaluatorConfig": {
    "name": "LLMJudgeTrajectorySimulationEvaluator",
    "model": "gpt-4o-2024-11-20",
    "temperature": 0.0
  }
}
```

Test with mocked tools:
- Simulate search_flights returning 3 options
- Simulate book_flight returning confirmation
- Simulate email sending returning success
- Agent should follow expected sequence with simulated responses
- **Score: ~0.9** based on behavior with mocked tools

## Best Practices

1. **Write clear behavior descriptions** - Be specific about expected sequences and decision logic
2. **Use temperature 0.0** for consistent evaluations
3. **Include context** - Provide enough detail in expected behavior
4. **Consider partial credit** - LLM can give partial scores for mostly correct trajectories
5. **Review justifications** - Understand why trajectories scored high or low

## When to Use vs Other Evaluators

### Use LLM Judge Trajectory when:
- Decision-making process matters more than just output
- Agent behavior patterns need validation
- Tool usage sequence is complex
- Human-like judgment of execution quality is needed
- Multiple valid execution paths exist

### Use Output-Based Evaluators when:
- Only final results matter
- What the agent produces is important
- How it got there is less important

## Configuration Tips

### Temperature Settings

- **0.0** (recommended): Deterministic, consistent results
- **0.1**: Slight variation for nuanced judgment
- **>0.3**: Not recommended (too inconsistent)

### Cost Optimization

- Token usage depends on trajectory length
- Cache evaluations for repeated runs
- Use in CI/CD pipelines carefully (may incur API costs)

## Error Handling

The evaluator will raise `UiPathEvaluationError` if:
- LLM service is unavailable
- Prompt doesn't contain required placeholders
- Agent trace cannot be converted to readable format
- LLM response cannot be parsed

## Performance Considerations

- **Token usage:** Trajectories can be long (more tokens used)
- **Evaluation time:** LLM calls take longer than deterministic evaluators
- **Caching:** Consider caching evaluations for repeated test runs
- **Batch processing:** Evaluate multiple trajectories in parallel when possible

## Related Evaluators

- [Tool Call Evaluators](tool-calls.md): For strict deterministic sequence validation
- [LLM Judge Output Evaluator](../output-based/llm-judge-output.md): For evaluating outputs instead of processes
- [Output-Based Evaluators](../output-based/index.md): For final result validation

## Next Steps

- [Back to Trajectory Overview](index.md)
- [Tool Call Evaluators](tool-calls.md)
- [Running Evaluations](../../running-evaluations.md)
- [Best Practices](../../best-practices.md)
