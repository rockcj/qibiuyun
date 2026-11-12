"""Voice engine router – GET /api/voices.

向前端暴露可用的语音引擎（本地管线 / 火山引擎云端全双工），
前端据此决定语音区域的选项是否可点。
"""

from fastapi import APIRouter

from config import settings

router = APIRouter(prefix="/api", tags=["voices"])

VOICE_ENGINE_LOCAL = "local"
VOICE_ENGINE_VOLCENGINE = "volcengine"


def get_voice_engines() -> list[dict]:
    """返回语音引擎清单（含可用性与不可用原因）。"""
    cloud_available = settings.volcengine_speech_available
    cloud_reason = ""
    if not cloud_available:
        if not settings.volcengine_speech_enabled:
            cloud_reason = "云端语音已被关闭（VOLCENGINE_SPEECH_ENABLED=false）"
        else:
            cloud_reason = "缺少 VOLCENGINE_SPEECH_API_KEY 配置"

    return [
        {
            "id": VOICE_ENGINE_LOCAL,
            "displayName": "本地语音",
            "description": "本地 Whisper 识别 + 大模型对话 + EdgeTTS/浏览器朗读",
            "available": True,
            "reason": "",
            "latencyHint": "中等",
        },
        {
            "id": VOICE_ENGINE_VOLCENGINE,
            "displayName": "豆包实时语音",
            "description": "火山引擎豆包端到端实时语音（Seeduplex 全双工），音色更自然",
            "available": cloud_available,
            "reason": cloud_reason,
            "latencyHint": "低",
            "provider": "volcengine",
            "model": settings.volcengine_speech_model,
            "voice": settings.volcengine_speech_voice,
        },
    ]


@router.get("/voices")
async def list_voice_engines():
    """返回语音引擎列表、默认引擎与当前配置摘要。"""
    return {
        "voiceEngines": get_voice_engines(),
        "defaultEngine": settings.voice_engine_default,
        "audio": {
            "input": {"codec": "pcm16", "sampleRate": 16000},
            "output": {"cloud": {"codec": "pcm16", "sampleRate": 24000}},
        },
    }
