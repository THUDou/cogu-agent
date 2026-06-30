
import os

COMMAND = "encrypt"
DESCRIPTION = "Encrypt a PDF with password protection"
CATEGORY = "security"

PARAMS = [
    {"name": "input",          "type": "str",  "required": True,  "help": "Input PDF path"},
    {"name": "output",         "type": "str",  "required": True,  "help": "Output PDF path"},
    {"name": "user_password",  "type": "str",  "required": True,  "help": "User password (to open document)"},
    {"name": "owner_password", "type": "str",  "required": False, "help": "Owner password (defaults to user_password)"},
    {"name": "allow_print",    "type": "bool", "required": False, "default": True,  "help": "Allow printing"},
    {"name": "allow_modify",   "type": "bool", "required": False, "default": False, "help": "Allow modification"},
    {"name": "allow_copy",     "type": "bool", "required": False, "default": False, "help": "Allow copying"},
]


def handler(params):
    from pypdf import PdfReader, PdfWriter
    from pypdf.constants import UserAccessPermissions

    input_path = params["input"]
    output_path = params["output"]
    user_password = params["user_password"]
    owner_password = params.get("owner_password") or user_password
    allow_print = params.get("allow_print", True)
    allow_modify = params.get("allow_modify", False)
    allow_copy = params.get("allow_copy", False)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"文件不存在: {input_path}")

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    if reader.metadata:
        writer.add_metadata(reader.metadata)

    permissions = UserAccessPermissions(0)
    if allow_print:
        permissions |= UserAccessPermissions.PRINT | UserAccessPermissions.PRINT_TO_REPRESENTATION
    if allow_modify:
        permissions |= UserAccessPermissions.MODIFY | UserAccessPermissions.ADD_OR_MODIFY
    if allow_copy:
        permissions |= UserAccessPermissions.EXTRACT | UserAccessPermissions.EXTRACT_TEXT_AND_GRAPHICS

    writer.encrypt(
        user_password=user_password,
        owner_password=owner_password,
        use_128bit=True,
        permissions_flag=permissions,
    )

    with open(output_path, "wb") as f:
        writer.write(f)

    return {
        "success": True,
        "action": "encrypt",
        "page_count": len(reader.pages),
        "output": output_path
    }


if __name__ == "__main__":
    from pdfkit.base import main
    main(handler, params_schema=PARAMS, description=DESCRIPTION)
