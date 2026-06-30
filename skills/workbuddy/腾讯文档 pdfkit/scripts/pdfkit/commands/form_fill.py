
import json
import os

COMMAND = "form_fill"
DESCRIPTION = "填写 PDF 中的可填写表单字段。"
CATEGORY = "security"
PARAMS = [
    {"name": "input", "type": "str", "required": True, "help": "输入 PDF 路径"},
    {"name": "output", "type": "str", "required": True, "help": "输出 PDF 路径"},
    {"name": "fields", "type": "json", "required": True, "help": '字段列表 [{"field_id": "name", "value": "张三", "page": 1}, ...]'},
]


def _monkeypatch_pypdf_opt():
    try:
        from pypdf.generic import DictionaryObject
        from pypdf.constants import FieldDictionaryAttributes

        original_get_inherited = DictionaryObject.get_inherited

        def patched_get_inherited(self, key, default=None):
            result = original_get_inherited(self, key, default)
            if key == FieldDictionaryAttributes.Opt:
                if isinstance(result, list) and all(
                    isinstance(v, list) and len(v) == 2 for v in result
                ):
                    result = [r[0] for r in result]
            return result

        DictionaryObject.get_inherited = patched_get_inherited
    except (ImportError, AttributeError):
        pass  # pypdf 版本不兼容，跳过 monkeypatch


def _validate_field_value(field_info, field_value):
    field_type = field_info.get("type", "unknown")
    field_id = field_info["field_id"]

    if field_type == "checkbox":
        checked_val = field_info.get("checked_value")
        unchecked_val = field_info.get("unchecked_value")
        if checked_val and unchecked_val:
            if field_value != checked_val and field_value != unchecked_val:
                return (
                    f'字段 "{field_id}" 是 checkbox，值 "{field_value}" 无效。'
                    f'有效值：checked="{checked_val}", unchecked="{unchecked_val}"'
                )

    elif field_type == "radio_group":
        radio_options = field_info.get("radio_options", [])
        option_values = [opt.get("value", "") for opt in radio_options]
        if option_values and field_value not in option_values:
            return (
                f'字段 "{field_id}" 是 radio_group，值 "{field_value}" 无效。'
                f'有效值：{option_values}'
            )

    elif field_type == "choice":
        choice_options = field_info.get("choice_options", [])
        choice_values = [opt.get("value", "") for opt in choice_options]
        if choice_values and field_value not in choice_values:
            return (
                f'字段 "{field_id}" 是 choice，值 "{field_value}" 无效。'
                f'有效值：{choice_values}'
            )

    return None


def fill_pdf_fields(input_pdf_path, fields, output_pdf_path):
    from pypdf import PdfReader, PdfWriter

    _monkeypatch_pypdf_opt()

    reader = PdfReader(input_pdf_path)

    from pdfkit.commands.form_detect import detect_fillable_fields
    has_fillable, detected_fields = detect_fillable_fields(input_pdf_path)

    if not has_fillable:
        return {"success": False, "errors": ["该 PDF 没有可填写的表单字段"]}

    fields_by_id = {f["field_id"]: f for f in detected_fields}

    errors = []
    warnings = []
    for field in fields:
        fid = field.get("field_id")
        existing_field = fields_by_id.get(fid)

        if not existing_field:
            errors.append(f"字段 '{fid}' 不存在")
            continue

        if "page" in field and "page" in existing_field:
            if field["page"] != existing_field["page"]:
                errors.append(
                    f"字段 '{fid}' 页码错误：传入 {field['page']}，实际在第 {existing_field['page']} 页"
                )

        if "value" in field:
            err = _validate_field_value(existing_field, field["value"])
            if err:
                errors.append(err)

    if errors:
        return {"success": False, "errors": errors, "warnings": warnings}

    fields_by_page = {}
    for field in fields:
        if "value" in field:
            page = field.get("page")
            if page is None:
                detected = fields_by_id.get(field["field_id"])
                page = detected.get("page", 1) if detected else 1
            if page not in fields_by_page:
                fields_by_page[page] = {}
            fields_by_page[page][field["field_id"]] = field["value"]

    writer = PdfWriter(clone_from=reader)
    filled_count = 0
    for page, field_values in fields_by_page.items():
        writer.update_page_form_field_values(
            writer.pages[page - 1], field_values, auto_regenerate=False
        )
        filled_count += len(field_values)

    writer.set_need_appearances_writer(True)

    with open(output_pdf_path, "wb") as f:
        writer.write(f)

    result = {
        "success": True,
        "filled_count": filled_count,
        "output": output_pdf_path
    }
    if warnings:
        result["warnings"] = warnings

    return result


def handler(params):
    input_path = params["input"]
    output_path = params["output"]
    fields = params.get("fields", [])

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"文件不存在: {input_path}")

    if not fields:
        raise ValueError("'fields' 不能为空")

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if isinstance(fields, str):
        with open(fields, "r", encoding="utf-8") as f:
            fields = json.load(f)

    return fill_pdf_fields(input_path, fields, output_path)


if __name__ == "__main__":
    from pdfkit.base import main
    main(handler, PARAMS, DESCRIPTION)
