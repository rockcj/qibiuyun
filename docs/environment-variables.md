# OfferGPT 环境变量配置说明

## 配置原则

项目环境变量采用“默认配置 + 环境变量覆盖”的方案。可公开的默认值写入 `.env.example` 和配置脚本，密钥、密码、数据库连接串等敏感值只写入本地 `.env.local`。

`.env.local` 已被 `.gitignore` 忽略，禁止提交到仓库。

## 已确认默认配置

| 配置项 | 默认值 | 说明 |
|---|---|---|
| Database JDBC URL | `jdbc:postgresql://118.145.179.97:5432/offergpt` | 已连通的服务器 PostgreSQL JDBC 地址 |
| Database URL | `postgresql://118.145.179.97:5432/offergpt` | Python/FastAPI 兼容地址，可在密钥文件中覆盖账号密码版本 |
| Redis Host | `118.145.179.97` | 使用服务器 Redis |
| Redis Port | `6379` | Redis 默认端口 |
| Redis DB | `1` | 固定使用 DB1，DB0 已有数据不可使用 |
| 对象存储 | `tos` | 使用火山引擎 TOS |
| TOS Region | `cn-guangzhou` | 广州地域 |
| TOS Endpoint | `tos-cn-guangzhou.volces.com` | TOS API 地址 |
| TOS Bucket | `offer` | 默认存储桶 |
| TOS ACL | `private` | 默认私有，简历、音频和报告不公开 |
| LLM Provider | `deepseek` | 使用 DeepSeek |
| LLM Base URL | `https://api.deepseek.com/anthropic` | Anthropic 兼容接口 |
| LLM Model | `deepseekV4pro` | 实时对话模型 |
| Report Model | `deepseekV4pro` | 报告生成模型 |

## Windows 一键配置

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-env.ps1
```

脚本默认会交互式要求输入以下敏感配置。如果项目根目录存在 `.env.secrets.local`，脚本会优先读取该文件并跳过对应输入。

| 输入项 | 用途 |
|---|---|
| `DATABASE_URL` | 可选；默认使用服务器 PostgreSQL 地址，如需要账号密码则覆盖 |
| Redis 密码 | 生成 `REDIS_PASSWORD` 和 `REDIS_URL` |
| TOS Access Key ID | 生成 `TOS_ACCESS_KEY_ID` 和 `VOLCENGINE_ACCESS_KEY_ID` |
| TOS Secret Access Key | 生成 `TOS_SECRET_ACCESS_KEY` 和 `VOLCENGINE_SECRET_ACCESS_KEY` |
| DeepSeek API Key | 生成 `LLM_API_KEY` 和 `DEEPSEEK_API_KEY` |

脚本执行后会生成：

```text
.env.local
```

## 给朋友的一键配置方式

如果需要给朋友一键配置，不要把真实密码写入文档或脚本。请在项目根目录单独准备一个不提交的 `.env.secrets.local` 文件，再让对方运行对应脚本。

`.env.secrets.local` 格式如下：

```text
DATABASE_URL=postgresql://user:password@server-host:5432/offergpt
DATABASE_JDBC_URL=jdbc:postgresql://118.145.179.97:5432/offergpt
REDIS_PASSWORD=替换为真实 Redis 密码
TOS_ACCESS_KEY_ID=替换为真实 TOS Access Key ID
TOS_SECRET_ACCESS_KEY=替换为真实 TOS Secret Access Key
DEEPSEEK_API_KEY=替换为真实 DeepSeek API Key
SESSION_TOKEN_SECRET=可选，不填则脚本自动生成
```

Windows 一键配置：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-env.ps1
```

Linux/macOS 一键配置：

```bash
bash scripts/setup-env.sh
```

脚本会读取 `.env.secrets.local` 并生成 `.env.local`。这两个文件都被 `.gitignore` 忽略，不能提交。

## Linux/macOS 一键配置

在项目根目录执行：

```bash
bash scripts/setup-env.sh
```

脚本会生成本地 `.env.local`，并自动设置文件权限为 `600`。

## 手动配置

如果不使用脚本，可以复制模板：

```bash
cp .env.example .env.local
```

然后手动填写以下变量：

```text
DATABASE_URL=
DATABASE_JDBC_URL=
REDIS_PASSWORD=
REDIS_URL=
TOS_ACCESS_KEY_ID=
TOS_SECRET_ACCESS_KEY=
VOLCENGINE_ACCESS_KEY_ID=
VOLCENGINE_SECRET_ACCESS_KEY=
LLM_API_KEY=
DEEPSEEK_API_KEY=
SESSION_TOKEN_SECRET=
```

## 校验清单

配置完成后检查以下事项：

1. `DATABASE_JDBC_URL` 必须是 `jdbc:postgresql://118.145.179.97:5432/offergpt`，除非后续更换数据库。
2. `REDIS_URL` 末尾必须是 `/1`。
3. `TOS_ACL` 必须保持 `private`，除非后续明确需要公开静态资源。
4. `LLM_API_BASE_URL` 必须是 `https://api.deepseek.com/anthropic`。
5. `LLM_MODEL` 与 `LLM_REPORT_MODEL` 必须是 `deepseekV4pro`。
6. `.env.local` 不得被提交。
7. `.env.example` 不得出现真实密钥、密码或 Token。
