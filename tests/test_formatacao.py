from formatacao import moeda


def test_moeda_formato_brasileiro():
    assert moeda(1000) == "R$ 1.000,00"
    assert moeda(6579.32) == "R$ 6.579,32"
    assert moeda(1234567.9) == "R$ 1.234.567,90"


def test_moeda_valores_ausentes():
    assert moeda(0) == "R$ 0,00"
    assert moeda(None) == "R$ 0,00"


def test_moeda_valor_negativo():
    assert moeda(-150.5) == "R$ -150,50"
