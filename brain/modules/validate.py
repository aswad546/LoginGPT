import json
from marshmallow import ValidationError


def JsonString(json_string):
    try:
        json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON string: {e}")
