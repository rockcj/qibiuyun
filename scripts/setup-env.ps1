# OfferGPT Windows 环境变量配置脚本
# 运行方式：powershell -ExecutionPolicy Bypass -File scripts/setup-env.ps1

$ErrorActionPreference = "Stop"

function Convert-SecureValueToText {
    param(
        [Parameter(Mandatory = $true)]
        [System.Security.SecureString] $SecureValue
    )

    # 将交互输入的密钥写入本地 .env.local，仅用于本机开发，不提交仓库。
    $bstrPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstrPointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstrPointer)
    }
}

function Read-SecretText {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Prompt
    )

    $secureValue = Read-Host $Prompt -AsSecureString
    return Convert-SecureValueToText -SecureValue $secureValue
}

function New-SessionSecret {
    # 生成会话签名密钥，避免使用固定默认值。
    $randomBytes = New-Object byte[] 32
    $randomGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $randomGenerator.GetBytes($randomBytes)
        return [Convert]::ToBase64String($randomBytes)
    }
    finally {
        $randomGenerator.Dispose()
    }
}

function Import-SecretFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SecretFilePath
    )

    $secretValues = @{}
    if (-not (Test-Path $SecretFilePath)) {
        return $secretValues
    }

    # 读取本地密钥文件，格式为 KEY=VALUE；该文件被 .gitignore 忽略。
    Get-Content $SecretFilePath | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $key, $value = $line.Split("=", 2)
        $secretValues[$key.Trim()] = $value.Trim()
    }

    return $secretValues
}

function Read-ConfigValue {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable] $SecretValues,
        [Parameter(Mandatory = $true)]
        [string] $Key,
        [Parameter(Mandatory = $true)]
        [string] $Prompt,
        [bool] $IsSecret = $false
    )

    if ($SecretValues.ContainsKey($Key) -and $SecretValues[$Key]) {
        return $SecretValues[$Key]
    }

    if ($IsSecret) {
        return Read-SecretText -Prompt $Prompt
    }

    return Read-Host $Prompt
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$envFilePath = Join-Path $projectRoot ".env.local"
$secretFilePath = Join-Path $projectRoot ".env.secrets.local"

Write-Host "Generating OfferGPT local environment file: $envFilePath"
Write-Host "Secrets are written only to .env.local, which is ignored by git."
Write-Host "If .env.secrets.local exists, it will be loaded first."

$secretValues = Import-SecretFile -SecretFilePath $secretFilePath
$databaseJdbcUrl = "jdbc:postgresql://118.145.179.97:5432/offergpt"
$databaseHost = "118.145.179.97"
$databasePort = "5432"
$databaseName = "offergpt"
$databaseUser = "offergpt"
if ($secretValues.ContainsKey("DATABASE_JDBC_URL") -and $secretValues["DATABASE_JDBC_URL"]) {
    $databaseJdbcUrl = $secretValues["DATABASE_JDBC_URL"]
}
if ($secretValues.ContainsKey("DATABASE_HOST") -and $secretValues["DATABASE_HOST"]) {
    $databaseHost = $secretValues["DATABASE_HOST"]
}
if ($secretValues.ContainsKey("DATABASE_PORT") -and $secretValues["DATABASE_PORT"]) {
    $databasePort = $secretValues["DATABASE_PORT"]
}
if ($secretValues.ContainsKey("DATABASE_NAME") -and $secretValues["DATABASE_NAME"]) {
    $databaseName = $secretValues["DATABASE_NAME"]
}
if ($secretValues.ContainsKey("DATABASE_USER") -and $secretValues["DATABASE_USER"]) {
    $databaseUser = $secretValues["DATABASE_USER"]
}
$databasePassword = Read-ConfigValue -SecretValues $secretValues -Key "DATABASE_PASSWORD" -Prompt "Enter PostgreSQL password" -IsSecret $true
$databaseUrl = "postgresql://${databaseUser}:${databasePassword}@${databaseHost}:${databasePort}/${databaseName}"
if ($secretValues.ContainsKey("DATABASE_URL") -and $secretValues["DATABASE_URL"]) {
    $databaseUrl = $secretValues["DATABASE_URL"]
}
$volcengineAccessKeyId = ""
$volcengineSecretAccessKey = ""
if ($secretValues.ContainsKey("VOLCENGINE_ACCESS_KEY_ID") -and $secretValues["VOLCENGINE_ACCESS_KEY_ID"]) {
    $volcengineAccessKeyId = $secretValues["VOLCENGINE_ACCESS_KEY_ID"]
}
if ($secretValues.ContainsKey("VOLCENGINE_SECRET_ACCESS_KEY") -and $secretValues["VOLCENGINE_SECRET_ACCESS_KEY"]) {
    $volcengineSecretAccessKey = $secretValues["VOLCENGINE_SECRET_ACCESS_KEY"]
}
if (-not ($secretValues.ContainsKey("TOS_ACCESS_KEY_ID") -and $secretValues["TOS_ACCESS_KEY_ID"]) -and $volcengineAccessKeyId) {
    $secretValues["TOS_ACCESS_KEY_ID"] = $volcengineAccessKeyId
}
if (-not ($secretValues.ContainsKey("TOS_SECRET_ACCESS_KEY") -and $secretValues["TOS_SECRET_ACCESS_KEY"]) -and $volcengineSecretAccessKey) {
    $secretValues["TOS_SECRET_ACCESS_KEY"] = $volcengineSecretAccessKey
}
$redisPassword = Read-ConfigValue -SecretValues $secretValues -Key "REDIS_PASSWORD" -Prompt "Enter Redis password" -IsSecret $true
$tosAccessKeyId = Read-ConfigValue -SecretValues $secretValues -Key "TOS_ACCESS_KEY_ID" -Prompt "Enter TOS Access Key ID" -IsSecret $true
$tosSecretAccessKey = Read-ConfigValue -SecretValues $secretValues -Key "TOS_SECRET_ACCESS_KEY" -Prompt "Enter TOS Secret Access Key" -IsSecret $true
$deepseekApiKey = Read-ConfigValue -SecretValues $secretValues -Key "DEEPSEEK_API_KEY" -Prompt "Enter DeepSeek API Key" -IsSecret $true

if ($secretValues.ContainsKey("SESSION_TOKEN_SECRET") -and $secretValues["SESSION_TOKEN_SECRET"]) {
    $sessionSecret = $secretValues["SESSION_TOKEN_SECRET"]
}
else {
    $sessionSecret = New-SessionSecret
}

$envContent = @"
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
SESSION_TOKEN_SECRET=$sessionSecret
SESSION_TTL_SECONDS=7200
REQUEST_TIMEOUT_SECONDS=30
LOG_LEVEL=INFO

DATABASE_JDBC_URL=$databaseJdbcUrl
DATABASE_HOST=$databaseHost
DATABASE_PORT=$databasePort
DATABASE_NAME=$databaseName
DATABASE_USER=$databaseUser
DATABASE_PASSWORD=$databasePassword
DATABASE_URL=$databaseUrl

REDIS_HOST=118.145.179.97
REDIS_PORT=6379
REDIS_DB=1
REDIS_PASSWORD=$redisPassword
REDIS_URL=redis://:$redisPassword@118.145.179.97:6379/1

OBJECT_STORAGE_PROVIDER=tos
TOS_ENDPOINT=tos-cn-guangzhou.volces.com
TOS_REGION=cn-guangzhou
TOS_BUCKET=offer
TOS_ACL=private
TOS_ACCESS_KEY_ID=$tosAccessKeyId
TOS_SECRET_ACCESS_KEY=$tosSecretAccessKey
VOLCENGINE_ACCESS_KEY_ID=$tosAccessKeyId
VOLCENGINE_SECRET_ACCESS_KEY=$tosSecretAccessKey
TOS_PUBLIC_BASE_URL=
LOCAL_STORAGE_DIR=./storage

LLM_PROVIDER=deepseek
LLM_API_BASE_URL=https://api.deepseek.com/anthropic
LLM_MODEL=deepseekV4pro
LLM_REPORT_MODEL=deepseekV4pro
LLM_API_KEY=$deepseekApiKey
DEEPSEEK_API_BASE_URL=https://api.deepseek.com/anthropic
DEEPSEEK_API_KEY=$deepseekApiKey
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
"@

Set-Content -Path $envFilePath -Value $envContent -Encoding UTF8
Write-Host ".env.local generated. Do not commit this file."
