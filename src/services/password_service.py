from pwdlib import PasswordHash

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


# 不存在的帳號也做雜湊驗證，減少可用來推測帳號存在與否的時間差。
DUMMY_HASH = password_hasher.hash("dummy-password-not-a-real-account")


def verify_password(password: str, encoded: str) -> bool:
    return password_hasher.verify(password, encoded)
