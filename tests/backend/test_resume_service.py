"""简历服务单元测试 – 文本抽取、文件类型检测、解析流程。"""

import pytest

from services.resume_service import (
    detect_file_type,
    extract_text_from_file,
    parse_resume,
)


class TestDetectFileType:
    """文件类型检测测试。"""

    def test_detect_pdf_by_extension(self):
        """应根据扩展名识别 PDF。"""
        assert detect_file_type("resume.pdf", None) == "pdf"

    def test_detect_txt_by_extension(self):
        """应根据扩展名识别 TXT。"""
        assert detect_file_type("resume.txt", None) == "txt"

    def test_detect_pdf_by_mime(self):
        """应根据 MIME 类型识别 PDF。"""
        assert detect_file_type("file", "application/pdf") == "pdf"


class TestExtractTextFromFile:
    """文本抽取测试。"""

    def test_extract_txt_content(self):
        """应正确解码 UTF-8 文本文件。"""
        content = "Hello Resume\nPython Developer"
        text = extract_text_from_file(content.encode("utf-8"), "txt", "resume.txt")
        assert "Python Developer" in text

    def test_extract_unsupported_type_raises(self):
        """不支持的文件类型应抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的文件类型"):
            extract_text_from_file(b"data", "docx", "resume.docx")

    def test_extract_empty_pdf_raises(self):
        """无法解析的 PDF 应抛出 ValueError。"""
        with pytest.raises(ValueError, match="无法解析 PDF"):
            extract_text_from_file(b"not-a-pdf", "pdf", "resume.pdf")


class TestParseResume:
    """简历解析集成测试。"""

    @pytest.mark.asyncio
    async def test_parse_resume_returns_profile(self, sample_resume_text):
        """parse_resume 应返回完整画像。"""
        profile = await parse_resume(sample_resume_text)
        assert "skills" in profile
        assert len(profile["skills"]) > 0
