"""密码哈希与验证 — bcrypt 直接调用（兼容 bcrypt 4.x / 5.x）。"""

import bcrypt


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希，返回字符串形式。"""
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与 bcrypt 哈希是否匹配。"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )
