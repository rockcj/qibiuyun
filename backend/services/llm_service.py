"""LLM 结构化提取服务 – 支持 DeepSeek API，无密钥时回退正则解析。"""

import json
import re
from typing import Any, Optional

import httpx

from config import settings

# 常见技术技能关键词，用于正则兜底提取
COMMON_SKILL_KEYWORDS = [
    "Python", "Java", "JavaScript", "TypeScript", "React", "Vue", "Angular",
    "Node.js", "FastAPI", "Django", "Flask", "Spring", "Go", "Rust", "C++",
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Docker", "Kubernetes",
    "AWS", "Azure", "GCP", "LLM", "RAG", "NLP", "Machine Learning", "Deep Learning",
    "TensorFlow", "PyTorch", "API Design", "System Design", "Microservices",
    "Git", "CI/CD", "Agile", "Scrum", "REST", "GraphQL", "HTML", "CSS",
    "Next.js", "Express", "Linux", "Kafka", "Elasticsearch", "Spark",
]

# JD 能力项关键词映射
COMPETENCY_KEYWORDS = {
    "systemDesign": ["system design", "architecture", "scalab", "distributed"],
    "problemSolving": ["problem solving", "troubleshoot", "debug", "analytical"],
    "communication": ["communication", "collaborat", "teamwork", "stakeholder"],
    "leadership": ["lead", "mentor", "manage", "supervis"],
    "technicalDepth": ["technical", "expert", "deep knowledge", "specialist"],
}


def _get_api_key() -> str:
    """获取 LLM API Key，优先使用 deepseek_api_key。"""
    return settings.deepseek_api_key or settings.llm_api_key


async def _call_llm_json(prompt: str, system: str) -> Optional[dict]:
    """调用 LLM 并解析 JSON 响应，失败时返回 None。"""
    api_key = _get_api_key()
    if not api_key:
        return None

    url = f"{settings.llm_api_base_url.rstrip('/')}/v1/messages"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.llm_model,
        "max_tokens": 2048,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                return None
            data = resp.json()
            # Anthropic 兼容格式
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            if not content:
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            # 提取 JSON 块
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                return json.loads(json_match.group())
    except Exception:
        return None
    return None


def extract_skills_by_regex(text: str) -> list[str]:
    """用正则从文本中匹配常见技能关键词。"""
    found: list[str] = []
    text_lower = text.lower()
    for skill in COMMON_SKILL_KEYWORDS:
        if skill.lower() in text_lower and skill not in found:
            found.append(skill)
    return found[:15]


def extract_projects_by_regex(text: str) -> list[dict]:
    """从简历文本中用简单规则提取项目片段。"""
    projects: list[dict] = []
    # 匹配 "Project: xxx" 或独立项目段落
    patterns = [
        r"(?:Project|项目)[:\s]+([^\n]{3,80})",
        r"([A-Z][A-Za-z0-9\s]{5,40}(?:System|Platform|App|Service|Tool))",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            name = match.group(1).strip()
            if name and not any(p["name"] == name for p in projects):
                projects.append({
                    "name": name,
                    "role": "Contributor",
                    "impact": "详见简历原文",
                })
            if len(projects) >= 5:
                break
    return projects


def extract_risk_signals_by_regex(text: str) -> list[str]:
    """检测简历中的潜在风险信号。"""
    risks: list[str] = []
    # 缺少量化指标
    if not re.search(r"\d+%|\d+\s*(?:ms|s|users|requests|QPS|million|k\b)", text, re.I):
        risks.append("Few quantified business outcomes")
    # 过短简历
    if len(text.strip()) < 200:
        risks.append("Resume content is too short for deep analysis")
    # 缺少项目经历关键词
    if not re.search(r"project|项目|experience|经历", text, re.I):
        risks.append("No clear project experience section detected")
    return risks


def extract_competencies_by_regex(jd_text: str) -> list[str]:
    """从 JD 文本中匹配能力项。"""
    found: list[str] = []
    jd_lower = jd_text.lower()
    for competency, keywords in COMPETENCY_KEYWORDS.items():
        if any(kw in jd_lower for kw in keywords):
            found.append(competency)
    if not found:
        found = ["problemSolving", "communication"]
    return found


def infer_difficulty_level(jd_text: str, title: str = "") -> str:
    """根据 JD 关键词推断难度等级。"""
    combined = (jd_text + " " + title).lower()
    if any(kw in combined for kw in ["senior", "lead", "principal", "architect", "5+ years", "8+ years"]):
        return "senior"
    if any(kw in combined for kw in ["junior", "entry", "graduate", "0-2 years", "fresh"]):
        return "junior"
    return "middle"


async def parse_resume_profile(raw_text: str) -> dict[str, Any]:
    """解析简历文本，返回结构化画像。"""
    system = (
        "You are a resume parser. Extract structured data from the resume text. "
        "Return ONLY valid JSON with keys: skills (string array), projects (array of "
        "{name, role, impact}), riskSignals (string array). Use English for field values."
    )
    prompt = f"Parse this resume:\n\n{raw_text[:6000]}"
    llm_result = await _call_llm_json(prompt, system)

    if llm_result and "skills" in llm_result:
        return {
            "skills": llm_result.get("skills", [])[:15],
            "projects": llm_result.get("projects", [])[:5],
            "riskSignals": llm_result.get("riskSignals", []),
        }

    # 正则兜底
    return {
        "skills": extract_skills_by_regex(raw_text),
        "projects": extract_projects_by_regex(raw_text),
        "riskSignals": extract_risk_signals_by_regex(raw_text),
    }


async def parse_job_profile(title: str, company: str, jd_text: str) -> dict[str, Any]:
    """解析 JD 文本，返回岗位画像。"""
    system = (
        "You are a job description parser. Extract structured data. "
        "Return ONLY valid JSON with keys: requiredSkills (string array), "
        "competencies (string array from: systemDesign, problemSolving, communication, "
        "leadership, technicalDepth), difficultyLevel (junior|middle|senior)."
    )
    prompt = f"Title: {title}\nCompany: {company}\n\nJD:\n{jd_text[:6000]}"
    llm_result = await _call_llm_json(prompt, system)

    if llm_result and "requiredSkills" in llm_result:
        return {
            "requiredSkills": llm_result.get("requiredSkills", [])[:15],
            "competencies": llm_result.get("competencies", []),
            "difficultyLevel": llm_result.get("difficultyLevel", "middle"),
        }

    # 正则兜底
    skills = extract_skills_by_regex(jd_text)
    if not skills:
        skills = ["Communication", "Problem Solving"]
    return {
        "requiredSkills": skills,
        "competencies": extract_competencies_by_regex(jd_text),
        "difficultyLevel": infer_difficulty_level(jd_text, title),
    }
