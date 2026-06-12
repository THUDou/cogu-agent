import csv
import io
import os
from pathlib import Path

from cogu.tools.base import FunctionTool, ToolRegistry, ToolCapability


def _pdf_read(path: str, pages: str = "") -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    try:
        from pypdf import PdfReader
    except ImportError:
        return "Error: pypdf not installed. Run: pip install pypdf"
    reader = PdfReader(str(p))
    total = len(reader.pages)
    page_nums = []
    if pages:
        for part in pages.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                page_nums.extend(range(int(a) - 1, int(b)))
            else:
                page_nums.append(int(part) - 1)
    else:
        page_nums = list(range(min(total, 50)))
    text_parts = []
    for i in page_nums:
        if 0 <= i < total:
            text_parts.append(f"--- Page {i + 1} ---\n{reader.pages[i].extract_text()}")
    result = "\n\n".join(text_parts)
    if len(page_nums) < total:
        result += f"\n\n[Showing pages {page_nums[0] + 1}-{page_nums[-1] + 1} of {total}]"
    return result


def _pdf_merge(output: str, inputs: str) -> str:
    try:
        from pypdf import PdfWriter, PdfReader
    except ImportError:
        return "Error: pypdf not installed. Run: pip install pypdf"
    writer = PdfWriter()
    for inp in inputs.split(","):
        inp = inp.strip()
        if not Path(inp).exists():
            return f"Error: file not found: {inp}"
        reader = PdfReader(inp)
        for page in reader.pages:
            writer.add_page(page)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    writer.write(output)
    return f"Merged {len(inputs.split(','))} files -> {output}"


def _pdf_split(path: str, output_dir: str, pages_per: int = 1) -> str:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return "Error: pypdf not installed. Run: pip install pypdf"
    reader = PdfReader(path)
    total = len(reader.pages)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for i in range(0, total, pages_per):
        writer = PdfWriter()
        for j in range(i, min(i + pages_per, total)):
            writer.add_page(reader.pages[j])
        fname = out / f"split_{i + 1}_{min(i + pages_per, total)}.pdf"
        writer.write(str(fname))
    return f"Split {total} pages into {out}"


def _docx_read(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    try:
        from docx import Document
    except ImportError:
        return "Error: python-docx not installed. Run: pip install python-docx"
    doc = Document(str(p))
    text = "\n".join(para.text for para in doc.paragraphs if para.text.strip())
    if not text:
        return "[document contains no text paragraphs]"
    if len(text) > 10000:
        text = text[:10000] + "\n\n[truncated]"
    return text


def _xlsx_read(path: str, sheet: str = "") -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    try:
        import openpyxl
    except ImportError:
        return "Error: openpyxl not installed. Run: pip install openpyxl"
    wb = openpyxl.load_workbook(str(p), data_only=True)
    ws = wb[sheet] if sheet else wb.active
    output = io.StringIO()
    writer = csv.writer(output)
    for row in ws.iter_rows(values_only=True):
        writer.writerow([str(c) if c is not None else "" for c in row])
    result = output.getvalue()
    if len(result) > 10000:
        result = result[:10000] + "\n\n[truncated]"
    return result


def register_office_tools(registry: ToolRegistry):
    registry.register(FunctionTool(_pdf_read, name="pdf_read", description="Read text from a PDF file. Specify pages like '1-5' or '1,3,5'.").with_capability(ToolCapability.READ_ONLY).mark_concurrency_safe().with_group("office"))
    registry.register(FunctionTool(_pdf_merge, name="pdf_merge", description="Merge multiple PDF files into one. Inputs as comma-separated paths.").with_capability(ToolCapability.WRITES_FILES).with_group("office"))
    registry.register(FunctionTool(_pdf_split, name="pdf_split", description="Split a PDF into multiple files by page count.").with_capability(ToolCapability.WRITES_FILES).with_group("office"))
    registry.register(FunctionTool(_docx_read, name="docx_read", description="Read text content from a .docx Word document.").with_capability(ToolCapability.READ_ONLY).mark_concurrency_safe().with_group("office"))
    registry.register(FunctionTool(_xlsx_read, name="xlsx_read", description="Read data from an Excel spreadsheet as CSV. Specify sheet name optionally.").with_capability(ToolCapability.READ_ONLY).mark_concurrency_safe().with_group("office"))
