#!/usr/bin/env python3
"""라이선스 문자열 → (분류, 상업 이용 가능 여부). 책 출판의 생명선 — grab·classify·storage가 모두 이 한 곳을 쓴다.
순서가 중요하다: PD/CC0 → NC/ND(불가) → SA/BY(가능) → ⓒ → unknown."""
import re

LICENSE_TABLE = [
    (re.compile(r"public\s*domain|\bpd\b|pd-us|pd-old|pd-art|pdm|no known copyright|cc-pd|publicdomain|퍼블릭\s*도메인|공유\s*저작물", re.I), "PD", True),
    (re.compile(r"\bcc0\b|cc-zero|creative commons zero|cc0 1\.0", re.I), "CC0", True),
    (re.compile(r"\bby[-\s_]?nc|non[-\s]?commercial|비영리", re.I), "CC-BY-NC", False),
    (re.compile(r"\bby[-\s_]?nd|no[-\s]?deriv|변경\s*금지", re.I), "CC-BY-ND", False),
    (re.compile(r"\bby[-\s_]?sa", re.I), "CC-BY-SA", True),
    (re.compile(r"\bcc[-\s_]?by\b|\bcc\s*by\s*\d|attribution(?!.*non)", re.I), "CC-BY", True),
    (re.compile(r"\bgfdl\b|gnu free documentation", re.I), "GFDL", True),
    (re.compile(r"©|\(c\)|ⓒ|copyright|all rights reserved|trustees of|저작권|rights reserved", re.I), "ⓒ", False),
]

def license_class(text) -> tuple:
    """예: "CC BY-SA 4.0"→("CC-BY-SA",True) · "Public domain"→("PD",True) · "CC BY-NC-ND"→("CC-BY-NC",False)
    · "© Trustees of the British Museum"→("ⓒ",False) · None/""→("unknown",None)"""
    if not text or not str(text).strip(): return ("unknown", None)
    s = str(text)
    for rx, cls, ok in LICENSE_TABLE:
        if rx.search(s): return (cls, ok)
    return ("unknown", None)

def commercial_ok(text) -> bool | None:
    return license_class(text)[1]
