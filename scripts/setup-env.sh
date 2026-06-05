#!/usr/bin/env bash
# OfferGPT Linux/macOS 环境变量配置脚本
# 运行方式：bash scripts/setup-env.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env.local"
SECRET_FILE="$PROJECT_ROOT/.env.secrets.local"

echo "开始生成 OfferGPT 本地环境变量文件：$ENV_FILE"
echo "提示：密钥只会写入 .env.local，该文件已被 .gitignore 忽略。"
echo "如果存在 .env.secrets.local，将优先读取其中的密钥。"

if [[ -f "$SECRET_FILE" ]]; then
  # 读取本地密钥文件，格式为 KEY=VALUE；该文件被 .gitignore 忽略。
  set -a
  # shellcheck disable=SC1090
  source "$SECRET_FILE"
  set +a
fi

read_required_value() {
  local variable_name="$1"
  local prompt_text="$2"
  local current_value="${!variable_name:-}"

  if [[ -n "$current_value" ]]; then
    printf '%s' "$current_value"
    return
  fi

  read -r -p "$prompt_text" input_value
  printf '%s' "$input_value"
}

read_required_secret() {
  local variable_name="$1"
  local prompt_text="$2"
  local current_value="${!variable_name:-}"

  if [[ -n "$current_value" ]]; then
    printf '%s' "$current_value"
    return
  fi

  read -r -s -p "$prompt_text" input_value
  echo >&2
  printf '%s' "$input_value"
}

DATABASE_JDBC_URL="${DATABASE_JDBC_URL:-jdbc:postgresql://118.145.179.97:5432/offergpt}"
DATABASE_URL="${DATABASE_URL:-postgresql://118.145.179.97:5432/offergpt}"
REDIS_PASSWORD="$(read_required_secret "REDIS_PASSWORD" "请输入 Redis 密码: ")"
TOS_ACCESS_KEY_ID="$(read_required_secret "TOS_ACCESS_KEY_ID" "请输入 TOS Access Key ID: ")"
TOS_SECRET_ACCESS_KEY="$(read_required_secret "TOS_SECRET_ACCESS_KEY" "请输入 TOS Secret Access Key: ")"
DEEPSEEK_API_KEY="$(read_required_secret "DEEPSEEK_API_KEY" "请输入 DeepSeek API Key: ")"

# 生成会话签名密钥，避免使用固定默认值。
if [[ -n "${SESSION_TOKEN_SECRET:-}" ]]; then
  SESSION_TOKEN_SECRET="$SESSION_TOKEN_SECRET"
elif command -v openssl >/dev/null 2>&1; then
  SESSION_TOKEN_SECRET="$(openssl rand -base64 32)"
else
  SESSION_TOKEN_SECRET="$(date +%s%N | sha256sum | awk '{print $1}')"
fi

cat > "$ENV_FILE" <<EOF
APP_ENV=development
APP_NAME=OfferGPT
APP_BASE_URL=http://localhost:3000
API_BASE_URL=http://localhost:8000
WS_BASE_URL=ws://localhost:8000
DEFAULT_SCENE=interview
ENABLE_RESTAURANT_SCENE=false
ENABLE_MEETING_SCENE=false
REALTIME_LIGHT_CORRECTION_ENABLED=true
DEMO_MODE_ENABLED=true

BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ALLOW_ORIGINS=http://localhost:3000
SESSION_TOKEN_SECRET=$SESSION_TOKEN_SECRET
SESSION_TTL_SECONDS=7200
REQUEST_TIMEOUT_SECONDS=30
LOG_LEVEL=INFO

DATABASE_JDBC_URL=$DATABASE_JDBC_URL
DATABASE_URL=$DATABASE_URL

REDIS_HOST=118.145.179.97
REDIS_PORT=6379
REDIS_DB=1
REDIS_PASSWORD=$REDIS_PASSWORD
REDIS_URL=redis://:$REDIS_PASSWORD@118.145.179.97:6379/1

OBJECT_STORAGE_PROVIDER=tos
TOS_ENDPOINT=tos-cn-guangzhou.volces.com
TOS_REGION=cn-guangzhou
TOS_BUCKET=offer
TOS_ACL=private
TOS_ACCESS_KEY_ID=$TOS_ACCESS_KEY_ID
TOS_SECRET_ACCESS_KEY=$TOS_SECRET_ACCESS_KEY
VOLCENGINE_ACCESS_KEY_ID=$TOS_ACCESS_KEY_ID
VOLCENGINE_SECRET_ACCESS_KEY=$TOS_SECRET_ACCESS_KEY
TOS_PUBLIC_BASE_URL=
LOCAL_STORAGE_DIR=./storage

LLM_PROVIDER=deepseek
LLM_API_BASE_URL=https://api.deepseek.com/anthropic
LLM_MODEL=deepseekV4pro
LLM_REPORT_MODEL=deepseekV4pro
LLM_API_KEY=$DEEPSEEK_API_KEY
DEEPSEEK_API_BASE_URL=https://api.deepseek.com/anthropic
DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY
OPENAI_API_KEY=

ASR_PROVIDER=whisper
ASR_API_BASE_URL=
ASR_API_KEY=
ASR_MODEL=whisper-1

TTS_PROVIDER=edgeTts
TTS_API_BASE_URL=
TTS_API_KEY=
TTS_VOICE=en-US-JennyNeural
AI_PROVIDER_TIMEOUT_SECONDS=20

NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000
NEXT_PUBLIC_DEFAULT_SCENE=interview
NEXT_PUBLIC_DEMO_MODE_ENABLED=true
NEXT_PUBLIC_ENABLE_RESTAURANT_SCENE=false
NEXT_PUBLIC_ENABLE_MEETING_SCENE=false

ENABLE_TEXT_INPUT_FALLBACK=true
ENABLE_MOCK_ASR=true
ENABLE_MOCK_TTS=true
ENABLE_PRESET_DEMO_DATA=true
ENABLE_REPORT_RETRY=true
REPORT_FALLBACK_MODE=basicTemplate

TEST_DEFAULT_SCENE=interview
TEST_USE_MOCK_AI=true
TEST_USE_MOCK_AUDIO=true
TEST_DEMO_RESUME_PATH=./demo/resume.txt
TEST_DEMO_JD_PATH=./demo/jd.txt
EOF

chmod 600 "$ENV_FILE"
echo "已生成 .env.local。请不要提交该文件。"
