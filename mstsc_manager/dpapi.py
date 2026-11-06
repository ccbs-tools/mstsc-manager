"""Windows DPAPI 封装：加密结果只能由当前 Windows 用户在本机解密。"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt

_crypt32 = ctypes.windll.crypt32
_kernel32 = ctypes.windll.kernel32

_ENTROPY = b"mstsc-manager/v1"


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _DATA_BLOB:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _take(blob: _DATA_BLOB) -> bytes:
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        _kernel32.LocalFree(blob.pbData)


def protect(plain: str) -> str:
    if not plain:
        return ""
    src = _blob(plain.encode("utf-8"))
    ent = _blob(_ENTROPY)
    out = _DATA_BLOB()
    if not _crypt32.CryptProtectData(ctypes.byref(src), None, ctypes.byref(ent), None, None, 0, ctypes.byref(out)):
        raise ctypes.WinError()
    return base64.b64encode(_take(out)).decode("ascii")


def unprotect(enc: str) -> str:
    if not enc:
        return ""
    src = _blob(base64.b64decode(enc))
    ent = _blob(_ENTROPY)
    out = _DATA_BLOB()
    if not _crypt32.CryptUnprotectData(ctypes.byref(src), None, ctypes.byref(ent), None, None, 0, ctypes.byref(out)):
        raise ctypes.WinError()
    return _take(out).decode("utf-8")
