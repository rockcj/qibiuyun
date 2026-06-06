-- OfferGPT 认证系统迁移
-- 为 users 表新增 hashed_password 字段（nullable，兼容 demo 用户）
-- 执行方式: psql -h <host> -U <user> -d <db> -f migrations/002_add_password.sql

BEGIN;
ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password VARCHAR(255);
COMMIT;
