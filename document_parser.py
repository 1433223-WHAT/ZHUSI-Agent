"""Safe text extraction for user-supplied project documents."""

from __future__ import annotations

import io
import re
import tempfile
import time
import uuid
from pathlib import Path

from docx import Document
from pypdf import PdfReader


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 120_000
SUPPORTED = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pdf": "application/pdf",
}


class DocumentParseError(ValueError):
    pass


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocumentParseError("无法识别文本编码，请将文件保存为 UTF-8 后重试。")


def _parse_docx(data: bytes) -> str:
    if not data.startswith(b"PK"):
        raise DocumentParseError("文件扩展名为 DOCX，但内容不是有效的 DOCX 文件。")
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise DocumentParseError("DOCX 文件损坏或无法读取。") from exc
    blocks = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                blocks.append(" | ".join(cells))
    return "\n".join(blocks)


def _parse_legacy_doc(data: bytes) -> str:
    if not data.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        raise DocumentParseError("文件扩展名为 DOC，但内容不是有效的旧版 Word 文件。")
    try:
        import pythoncom
        import pywintypes
        import win32com.client
    except ImportError as exc:
        raise DocumentParseError("读取旧版 DOC 需要本机 Microsoft Word 和 pywin32；也可以先另存为 DOCX。") from exc

    temp_path = Path(tempfile.gettempdir()) / f"zhusi-{uuid.uuid4().hex}.doc"
    temp_path.write_bytes(data)
    word = None
    document = None
    pythoncom.CoInitialize()
    try:
        last_error = None
        for attempt in range(3):
            try:
                word = win32com.client.DispatchEx("Word.Application")
                word.Visible = False
                word.DisplayAlerts = 0
                document = word.Documents.Open(str(temp_path), False, True, False)
                text = str(document.Content.Text or "")
                if not text.strip():
                    raise DocumentParseError("旧版 DOC 中没有提取到可读文字。")
                return text
            except DocumentParseError:
                raise
            except (pywintypes.com_error, AttributeError) as exc:
                last_error = exc
                if document is not None:
                    try:
                        document.Close(False)
                    except Exception:
                        pass
                    document = None
                if word is not None:
                    try:
                        word.Quit()
                    except Exception:
                        pass
                    word = None
                time.sleep(0.4 * (attempt + 1))
        raise DocumentParseError(
            "旧版 DOC 无法通过本机 Word 读取。请关闭可能弹窗或忙碌的 Word/WPS 后重试，或另存为 DOCX。"
        ) from last_error
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
        try:
            temp_path.unlink()
        except OSError:
            pass


def _parse_pdf(data: bytes) -> tuple[str, int]:
    if not data.startswith(b"%PDF-"):
        raise DocumentParseError("文件扩展名为 PDF，但内容不是有效的 PDF 文件。")
    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)
    except Exception as exc:
        raise DocumentParseError("PDF 文件损坏、已加密或无法读取。") from exc
    return text, len(reader.pages)


def parse_document(filename: str, data: bytes) -> dict:
    safe_name = Path(filename or "").name
    extension = Path(safe_name).suffix.lower()
    if extension not in SUPPORTED:
        raise DocumentParseError("仅支持 PDF、DOCX、TXT 和 MD 文档。")
    if not data:
        raise DocumentParseError("文件内容为空。")
    if len(data) > MAX_FILE_BYTES:
        raise DocumentParseError("文件超过 10 MB 限制。")

    page_count = None
    if extension in {".txt", ".md"}:
        text = _decode_text(data)
    elif extension == ".docx":
        text = _parse_docx(data)
    elif extension == ".doc":
        text = _parse_legacy_doc(data)
    else:
        text, page_count = _parse_pdf(data)

    text = _normalize(text)
    truncated = len(text) > MAX_TEXT_CHARS
    text = text[:MAX_TEXT_CHARS]
    status = "parsed" if text else ("ocr_required" if extension == ".pdf" else "empty")
    return {
        "filename": safe_name,
        "extension": extension,
        "mime_type": SUPPORTED[extension],
        "size_bytes": len(data),
        "status": status,
        "text": text,
        "character_count": len(text),
        "page_count": page_count,
        "truncated": truncated,
        "message": (
            "PDF 未提取到可复制文字，可能是扫描件，需要 OCR。"
            if status == "ocr_required"
            else "文档解析完成。" if status == "parsed" else "文档中没有可读取文字。"
        ),
    }
