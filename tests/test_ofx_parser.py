from ofx_parser import decode_ofx_bytes, parse_ofx

SAMPLE_OFX = """
OFXHEADER:100
DATA:OFXSGML
ENCODING:USASCII
<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKACCTFROM>
<BANKID>756
<BRANCHID>4406-7
<ACCTID>4928-0
</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260721120000
<TRNAMT>977.59
<FITID>2026072100112233
<NAME>SUHAI SEGURADORA
<MEMO>Recebimento Pix
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


def test_parses_reference_suhai_transaction():
    transactions = parse_ofx(SAMPLE_OFX)
    assert len(transactions) == 1
    txn = transactions[0]
    assert txn.account.bank_id == "756"
    assert txn.account.branch_id == "4406-7"
    assert txn.account.acct_id == "4928-0"
    assert txn.date == "2026-07-21"
    assert txn.amount == 977.59
    assert "SUHAI SEGURADORA" in txn.description
    assert txn.fit_id == "2026072100112233"


def test_decode_ofx_bytes_handles_utf8():
    text = "<OFX><NAME>Teste açúcar</NAME></OFX>"
    assert decode_ofx_bytes(text.encode("utf-8")) == text


def test_decode_ofx_bytes_falls_back_to_windows_1252():
    text = "<OFX>\r\nENCODING:1252\r\n<NAME>Cliente Ação</NAME></OFX>"
    raw = text.encode("windows-1252")
    assert "Ação" in decode_ofx_bytes(raw)


def test_negative_amount_parsed_for_cancellation():
    ofx = SAMPLE_OFX.replace("977.59", "-150.00")
    transactions = parse_ofx(ofx)
    assert transactions[0].amount == -150.00
