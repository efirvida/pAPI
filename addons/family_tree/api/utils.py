import re
from datetime import date, datetime
from typing import Union, get_args, get_origin

TYPE_MAP = {
    str: "text",
    int: "number",
    float: "number",
    bool: "checkbox",
    date: "date",
    datetime: "datetime-local",
}


def field_name_to_label(field_name: str) -> str:
    """Convierte snake_case a Human Readable Label"""
    return re.sub(r"_+", " ", field_name).title()


def model_to_form_schema(model):
    schema = []
    for field_name, field in model.model_fields.items():
        annotation = field.annotation
        args = get_args(annotation)
        origin = get_origin(annotation)

        is_optional = origin is Union and type(None) in args

        if is_optional:
            non_none_args = [arg for arg in args if arg is not type(None)]
            actual_type = non_none_args[0]
        else:
            actual_type = annotation

        field_type = TYPE_MAP.get(actual_type, "text")
        if field_name in ("avatar", "image", "photo"):
            field_type = "image"

        if field_name in ("description", "biography"):
            field_type = "textarea"

        schema.append({
            "id": field_name,
            "label": field_name_to_label(field_name),
            "required": not is_optional,
            "type": field_type,
        })
    return schema
