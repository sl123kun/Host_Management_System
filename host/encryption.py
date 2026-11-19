import os
from cryptography.fernet import Fernet, InvalidToken

def get_fernet():
    """
    从环境变量读取加密密钥。
    """

    key = os.getenv("FERNET_KEY")

    if not key:
        raise RuntimeError("未配置 FERNET_KEY 环境变量")

    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("FERNET_KEY 配置格式不正确") from exc


def encrypt_password(password: str) -> str:
    """
    加密主机登录密码。
    """

    if not password:
        raise ValueError("密码不能为空")

    fernet = get_fernet()

    encrypted = fernet.encrypt(password.encode("utf-8"))

    return encrypted.decode("utf-8")


def decrypt_password(encrypted_password: str) -> str:
    """
    解密主机登录密码。
    """

    if not encrypted_password:
        raise ValueError("加密密码不能为空")

    fernet = get_fernet()

    try:
        decrypted = fernet.decrypt(
            encrypted_password.encode("utf-8")
        )

        return decrypted.decode("utf-8")

    except InvalidToken as exc:
        raise ValueError("密码解密失败，密钥错误或密文已损坏") from exc
