"""Parser de extrato OFX.

Porta a lógica já validada em `Litor OFX - Atualizado/src/app.js`
(parsing por regex, fallback de encoding, dedup por FITID) para Python.
"""

import re
from dataclasses import dataclass

TAG_RE_CACHE: dict[str, re.Pattern] = {}


def _tag(block: str, name: str) -> str:
    pattern = TAG_RE_CACHE.get(name)
    if pattern is None:
        pattern = re.compile(
            rf"<{name}>\s*([\s\S]*?)(?=<\/?[A-Z0-9_]+(?:>|\s)|$)", re.IGNORECASE
        )
        TAG_RE_CACHE[name] = pattern
    match = pattern.search(block)
    return _clean_text(match.group(1)) if match else ""


def _clean_text(value: str) -> str:
    value = value or ""
    value = (
        value.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
    )
    value = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), value)
    return re.sub(r"\s+", " ", value).strip()


def decode_ofx_bytes(raw: bytes) -> str:
    header = raw[:2048].decode("windows-1252", errors="replace")
    declares_legacy = bool(
        re.search(
            r"(?:ENCODING|CHARSET)\s*:\s*(?:1252|WINDOWS-1252|ISO-8859-1|LATIN-?1)",
            header,
            re.IGNORECASE,
        )
    )
    utf8 = raw.decode("utf-8", errors="replace")
    if declares_legacy or "�" in utf8:
        return raw.decode("windows-1252", errors="replace")
    return utf8


def _transaction_description(item: str) -> str:
    fields = [_tag(item, "NAME"), _tag(item, "MEMO"), _tag(item, "PAYEEID")]
    fields = [f for f in fields if f]
    unique = []
    for i, value in enumerate(fields):
        lower = value.lower()
        if any(lower in other.lower() for other in fields[:i]):
            continue
        unique.append(value)
    return " - ".join(unique) or _tag(item, "TRNTYPE") or "Sem descrição"


def _parse_ofx_date(raw: str) -> str:
    match = re.match(r"^(\d{4})(\d{2})(\d{2})", raw or "")
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}" if match else ""


@dataclass
class OfxAccount:
    bank_id: str
    branch_id: str
    acct_id: str


@dataclass
class OfxTransaction:
    fit_id: str
    account: OfxAccount
    date: str  # YYYY-MM-DD
    description: str
    amount: float


def parse_ofx(text: str) -> list[OfxTransaction]:
    normalized = text.lstrip("﻿")
    account_blocks = re.findall(r"<STMTRS>([\s\S]*?)(?:</STMTRS>|$)", normalized, re.IGNORECASE)
    if not account_blocks:
        account_blocks = [normalized]

    transactions: list[OfxTransaction] = []
    for block in account_blocks:
        account = OfxAccount(
            bank_id=_tag(block, "BANKID"),
            branch_id=_tag(block, "BRANCHID"),
            acct_id=_tag(block, "ACCTID"),
        )
        entries = re.findall(
            r"<STMTTRN>([\s\S]*?)(?:</STMTTRN>|(?=<STMTTRN>)|$)", block, re.IGNORECASE
        )
        for item in entries:
            date = _parse_ofx_date(_tag(item, "DTPOSTED"))
            if not date:
                continue
            amount_raw = _tag(item, "TRNAMT").replace(",", ".")
            try:
                amount = float(amount_raw)
            except ValueError:
                amount = 0.0
            transactions.append(
                OfxTransaction(
                    fit_id=_tag(item, "FITID"),
                    account=account,
                    date=date,
                    description=_transaction_description(item),
                    amount=amount,
                )
            )
    return transactions
