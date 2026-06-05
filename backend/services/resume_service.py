"""简历上传、文本抽取与结构化解析服务。"""

import uuid
from pathlib import Path
from typing import Optional

from services.llm_service import parse_resume_profile

# 本地存储目录（TOS 不可用时的兜底）
LOCAL_STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage" / "resumes"


def extract_text_from_file(file_bytes: bytes, file_type: str, filename: str) -> str:
    """从上传文件中抽取纯文本。"""
    file_type = file_type.lower()

    if file_type in ("txt", "text", "plain"):
        return file_bytes.decode("utf-8", errors="ignore")

    if file_type == "pdf":
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(file_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages).strip()
            if text:
                return text
        except Exception:
            pass
        raise ValueError("无法解析 PDF 文件，请上传文本格式简历或确保 PDF 包含可选中文本层")

    raise ValueError(f"不支持的文件类型: {file_type}，请上传 PDF 或 TXT 文件")


def save_resume_file(file_bytes: bytes, filename: str) -> str:
    """将简历文件保存到本地存储，返回文件路径。"""
    LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = LOCAL_STORAGE_DIR / safe_name
    file_path.write_bytes(file_bytes)
    return str(file_path)


async def parse_resume(raw_text: str) -> dict:
    """调用 LLM/正则解析简历文本，返回结构化画像。"""
    return await parse_resume_profile(raw_text)


def detect_file_type(filename: str, content_type: Optional[str]) -> str:
    """根据文件名和 MIME 类型判断文件类型。"""
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in ("pdf", "txt"):
        return ext
    if content_type:
        if "pdf" in content_type:
            return "pdf"
        if "text" in content_type:
            return "txt"
    return ext or "txt"
