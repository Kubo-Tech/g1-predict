"""build_wsse_header の単体テスト"""

import base64
import re

from scripts.hatena_publish import build_wsse_header


# 正常系
def test_build_wsse_header_contains_username_token() -> None:
    """UsernameToken形式のヘッダを返す"""
    result = build_wsse_header("my_id", "my_key")
    assert result.startswith("UsernameToken ")


def test_build_wsse_header_contains_hatena_id() -> None:
    """はてなIDがUsernameフィールドに含まれる"""
    result = build_wsse_header("kubota_k", "api_key")
    assert 'Username="kubota_k"' in result


def test_build_wsse_header_contains_all_required_fields() -> None:
    """PasswordDigest, Nonce, Createdの全フィールドが含まれる"""
    result = build_wsse_header("my_id", "my_key")
    assert "PasswordDigest=" in result
    assert "Nonce=" in result
    assert "Created=" in result


def test_build_wsse_header_nonce_is_valid_base64() -> None:
    """NonceフィールドがBase64エンコードされた値である"""
    result = build_wsse_header("my_id", "my_key")
    match = re.search(r'Nonce="([^"]+)"', result)
    assert match is not None
    base64.b64decode(match.group(1))


def test_build_wsse_header_digest_is_valid_base64() -> None:
    """PasswordDigestフィールドがBase64エンコードされた値である"""
    result = build_wsse_header("my_id", "my_key")
    match = re.search(r'PasswordDigest="([^"]+)"', result)
    assert match is not None
    base64.b64decode(match.group(1))


def test_build_wsse_header_created_is_utc_format() -> None:
    """CreatedフィールドがISO 8601 UTC形式である"""
    result = build_wsse_header("my_id", "my_key")
    match = re.search(r'Created="([^"]+)"', result)
    assert match is not None
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", match.group(1))


def test_build_wsse_header_returns_different_nonce_each_call() -> None:
    """呼び出しごとにNonceが異なる（ランダム生成）"""
    result1 = build_wsse_header("my_id", "my_key")
    result2 = build_wsse_header("my_id", "my_key")
    nonce1 = re.search(r'Nonce="([^"]+)"', result1).group(1)  # type: ignore[union-attr]
    nonce2 = re.search(r'Nonce="([^"]+)"', result2).group(1)  # type: ignore[union-attr]
    assert nonce1 != nonce2
