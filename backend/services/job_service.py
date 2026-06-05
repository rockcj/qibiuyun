"""JD 输入、岗位画像与难度判断服务。"""

from services.llm_service import parse_job_profile


async def parse_job(title: str, company: str, jd_text: str) -> dict:
    """解析 JD 文本，返回岗位结构化画像。"""
    if not jd_text or not jd_text.strip():
        raise ValueError("JD 文本不能为空")
    if not title or not title.strip():
        raise ValueError("岗位名称不能为空")
    return await parse_job_profile(title.strip(), (company or "").strip(), jd_text.strip())
