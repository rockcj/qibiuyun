"""执行 PostgreSQL 数据库迁移。"""

from pathlib import Path

import psycopg2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE_PATH = PROJECT_ROOT / ".env.local"
MIGRATION_FILE_PATH = PROJECT_ROOT / "backend" / "migrations" / "001_init.sql"
EXPECTED_TABLES = (
    "users",
    "resumes",
    "jobs",
    "scene_presets",
    "interviews",
    "timeline_events",
    "reports",
    "agent_logs",
)


def loadLocalEnvironment() -> dict[str, str]:
    """从本地 .env.local 读取数据库连接配置，避免在脚本中硬编码密钥。"""
    environmentValues: dict[str, str] = {}
    for line in ENV_FILE_PATH.read_text(encoding="utf-8-sig").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        environmentValues[key] = value

    return environmentValues


def runMigration() -> None:
    """启用 pgcrypto 扩展，执行迁移 SQL，并校验核心表是否存在。"""
    environmentValues = loadLocalEnvironment()
    databaseUrl = environmentValues["DATABASE_URL"]
    migrationSql = MIGRATION_FILE_PATH.read_text(encoding="utf-8")

    connection = psycopg2.connect(databaseUrl)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            cursor.execute(migrationSql)
            cursor.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = 'public'
                  and table_name = any(%s)
                order by table_name;
                """,
                (list(EXPECTED_TABLES),),
            )

            createdTables = [row[0] for row in cursor.fetchall()]
            missingTables = sorted(set(EXPECTED_TABLES) - set(createdTables))
            print("created_tables=" + ",".join(createdTables))

            if missingTables:
                raise RuntimeError("missing_tables=" + ",".join(missingTables))
    finally:
        connection.close()


if __name__ == "__main__":
    runMigration()
