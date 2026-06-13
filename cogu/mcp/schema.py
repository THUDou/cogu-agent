from typing import Any


def normalize_schema_for_openai(schema: dict) -> dict:
    if not isinstance(schema, dict):
        return schema
    normalized = {}
    for key, value in schema.items():
        if key == "type" and isinstance(value, list):
            has_null = "null" in value
            non_null = [t for t in value if t != "null"]
            if non_null:
                normalized["type"] = non_null[0] if len(non_null) == 1 else non_null
            if has_null:
                normalized["nullable"] = True
        elif key == "properties" and isinstance(value, dict):
            normalized[key] = {k: normalize_schema_for_openai(v) for k, v in value.items()}
        elif key in ("items", "additionalProperties") and isinstance(value, dict):
            normalized[key] = normalize_schema_for_openai(value)
        elif key in ("allOf", "anyOf", "oneOf") and isinstance(value, list):
            normalized[key] = [normalize_schema_for_openai(item) for item in value]
        elif key == "$defs" and isinstance(value, dict):
            normalized[key] = {k: normalize_schema_for_openai(v) for k, v in value.items()}
        elif key == "definitions" and isinstance(value, dict):
            normalized[key] = {k: normalize_schema_for_openai(v) for k, v in value.items()}
        else:
            normalized[key] = value
    return normalized
