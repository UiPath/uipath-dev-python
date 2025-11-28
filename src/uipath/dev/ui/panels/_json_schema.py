from typing import Any


def mock_json_from_schema(schema: dict[str, Any]) -> Any:
    """Generate a mock JSON value based on a given JSON schema.

    - For object schemas: returns a dict of mocked properties.
    - For arrays: returns a list with one mocked item.
    - For primitives: returns a sensible example / default / enum[0].
    - Handles oneOf/anyOf by choosing the first option.
    - Special handling for LangChain message types.
    """

    def _is_langchain_messages_array(sub_schema: dict[str, Any]) -> bool:
        """Check if this is a LangChain messages array."""
        if sub_schema.get("type") != "array":
            return False
        items = sub_schema.get("items", {})
        if not isinstance(items, dict):
            return False
        # Check if it has oneOf with message types
        one_of = items.get("oneOf", [])
        if not one_of:
            return False
        # Look for HumanMessage or similar patterns
        for option in one_of:
            if isinstance(option, dict):
                title = option.get("title", "")
                if "Message" in title:
                    return True
        return False

    def _mock_langchain_human_message() -> dict[str, Any]:
        """Generate a mock HumanMessage for LangChain."""
        return {"type": "human", "content": "What's the weather like today?"}

    def _mock_value(
        sub_schema: dict[str, Any], required: bool = True, parent_key: str = ""
    ) -> Any:
        # 1) Default wins
        if "default" in sub_schema:
            return sub_schema["default"]

        # 2) Special handling for LangChain messages array
        if parent_key == "messages" and _is_langchain_messages_array(sub_schema):
            return [_mock_langchain_human_message()]

        # 3) Handle oneOf/anyOf - pick the first option (or HumanMessage if available)
        if "oneOf" in sub_schema and isinstance(sub_schema["oneOf"], list):
            if sub_schema["oneOf"]:
                # Try to find HumanMessage first
                for option in sub_schema["oneOf"]:
                    if (
                        isinstance(option, dict)
                        and option.get("title") == "HumanMessage"
                    ):
                        return _mock_value(option, required)
                # Otherwise use first option
                return _mock_value(sub_schema["oneOf"][0], required)
            return None

        if "anyOf" in sub_schema and isinstance(sub_schema["anyOf"], list):
            if sub_schema["anyOf"]:
                return _mock_value(sub_schema["anyOf"][0], required)
            return None

        t = sub_schema.get("type")

        # 4) Enums: pick the first option
        enum = sub_schema.get("enum")
        if enum and isinstance(enum, list):
            return enum[0]

        # 5) Handle const values
        if "const" in sub_schema:
            return sub_schema["const"]

        # 6) Objects: recurse into mock_json_from_schema
        if t == "object":
            if "properties" not in sub_schema:
                return {}
            return mock_json_from_schema(sub_schema)

        # 7) Arrays: mock a single item based on "items" schema
        if t == "array":
            item_schema = sub_schema.get("items", {})
            # If items is not a dict, just return empty list
            if not isinstance(item_schema, dict):
                return []
            return [_mock_value(item_schema, required=True)]

        # 8) Primitives
        if t == "string":
            # Check for specific titles that might indicate what example to use
            title = sub_schema.get("title", "").lower()
            if "content" in title:
                return "What's the weather like today?"
            # If there's a format, we could specialize later (email, date, etc.)
            return "example" if required else ""

        if t == "integer":
            return 0

        if t == "number":
            return 0.0

        if t == "boolean":
            return True if required else False

        # 9) Fallback
        return None

    # Top-level: if it's an object with properties, build a dict
    if schema.get("type") == "object":
        if "properties" not in schema:
            return {}

        props: dict[str, Any] = schema.get("properties", {})
        required_keys = set(schema.get("required", []))
        result: dict[str, Any] = {}

        for key, prop_schema in props.items():
            if not isinstance(prop_schema, dict):
                continue
            is_required = key in required_keys
            result[key] = _mock_value(prop_schema, required=is_required, parent_key=key)

        return result

    # If it's not an object schema, just mock the value directly
    return _mock_value(schema, required=True)
