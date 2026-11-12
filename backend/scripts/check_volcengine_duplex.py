"""火山引擎云端语音（Seeduplex 全双工）连通性自检脚本。

用法：
    # 1) 离线自检：校验 session.create 报文与事件桥接（无需 Key）
    python backend/scripts/check_volcengine_duplex.py

    # 2) 真实连通：连接云端，发送 1 秒 16kHz 静音，打印 8 秒内的下行事件
    python backend/scripts/check_volcengine_duplex.py --live

    # 3) 真实连通 + 文本播报（验证音色是否有效）
    python backend/scripts/check_volcengine_duplex.py --live --say "Hello, welcome to the interview."

需要环境变量（或 backend/.env / 根目录 .env.local）：
    VOLCENGINE_SPEECH_API_KEY     新版控制台 API Key（X-Api-Key）
    VOLCENGINE_SPEECH_APP_ID      可选
    VOLCENGINE_SPEECH_VOICE       音色名
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402
from services.volcengine import (  # noqa: E402
    DuplexEventBridge,
    VolcengineDuplexSession,
    build_session_object,
)


def run_offline_checks() -> bool:
    """离线自检：报文结构与事件桥接。"""
    ok = True

    session = build_session_object(
        voice=settings.volcengine_speech_voice or "test_voice",
        instructions="You are an English interviewer.",
    )
    assert session["model"], "model 不能为空"
    assert session["audio"]["input"]["format"]["rate"] == 16000
    assert session["audio"]["output"]["format"]["rate"] == 24000
    print(f"[OK] session.create payload: model={session['model']} "
          f"voice={session['audio']['output'].get('voice')}")

    counter = {"n": 0}

    def new_turn_id() -> str:
        counter["n"] += 1
        return f"turn_{counter['n']:03d}"

    bridge = DuplexEventBridge("selftest", new_turn_id)
    bridge.handle({"type": "conversation.item.input_audio_transcription.delta", "delta": "Hello"})
    final = bridge.handle({
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "Hello, I am here for the interview.",
    })
    assert final.messages[0]["type"] == "asr.final", final
    text = bridge.handle({"type": "response.output_text.delta", "delta": "Great."})
    assert text.messages[0]["type"] == "agent.text.delta"
    audio = bridge.handle({"type": "response.output_audio.delta", "delta": "AAAA"})
    assert audio.messages[0]["codec"] == "pcm16"
    print(f"[OK] bridge: {final.messages[0]['turnId']} transcript -> text -> pcm16 audio")

    return ok


async def run_live(say_text: str | None, seconds: float) -> int:
    """真实连通测试。"""
    if not settings.volcengine_speech_available:
        print("[SKIP] 未配置 VOLCENGINE_SPEECH_API_KEY，跳过真实连通测试")
        print("       在 backend/.env 或根目录 .env.local 中填入 API Key 后重试")
        return 2

    print(f"[LIVE] connecting {settings.volcengine_speech_ws_url}")
    session = VolcengineDuplexSession.from_settings(
        instructions="You are a friendly English interviewer. Reply in English."
    )
    try:
        await session.connect()
    except Exception as exc:
        print(f"[FAIL] 连接失败: {exc}")
        return 1

    print(f"[LIVE] session.id={session.session_id} logid={session.log_id}")

    async def pump() -> None:
        async for event in session.events():
            etype = event.get("type", "?")
            if etype == "response.output_audio.delta":
                size = len(str(event.get("delta") or event.get("audio") or ""))
                print(f"  <- audio delta base64_len={size}")
            elif etype in ("response.output_text.delta",):
                print(f"  <- text {event.get('delta')!r}")
            else:
                print(f"  <- {etype}")

    task = asyncio.create_task(pump())

    if say_text:
        print(f"[LIVE] say: {say_text}")
        await session.say(say_text)

    # 持续上行 1 秒 16kHz 静音，验证音频通道（20ms/包）
    silence = b"\x00" * 640
    for _ in range(50):
        await session.send_audio(silence)
        await asyncio.sleep(0.02)

    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=seconds)
    except asyncio.TimeoutError:
        pass
    finally:
        task.cancel()
        await session.close()

    print("[LIVE] done. 若上面出现 session.created 与响应事件，说明链路已打通。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Volcengine duplex voice self-check")
    parser.add_argument("--live", action="store_true", help="真实连接云端")
    parser.add_argument("--say", default=None, help="连接后让模型朗读的一段文本")
    parser.add_argument("--seconds", type=float, default=8.0, help="监听下行事件时长")
    args = parser.parse_args()

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    run_offline_checks()
    if not args.live:
        print("\n离线自检通过。加 --live 参数可测试真实云端链路。")
        return 0
    return asyncio.run(run_live(args.say, args.seconds))


if __name__ == "__main__":
    raise SystemExit(main())
