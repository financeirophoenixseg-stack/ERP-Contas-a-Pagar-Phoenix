"""Fixtures compartilhadas entre os testes."""

from types import SimpleNamespace


class _FakeQueryNot:
    """Suporta `.not_.is_(campo, "null")` -> campo IS NOT NULL."""

    def __init__(self, query: "_FakeQuery"):
        self._query = query

    def is_(self, campo, _valor):
        return _FakeQuery([d for d in self._query._dados if d.get(campo) is not None])


class _FakeQuery:
    """Substitui a cadeia de métodos do postgrest-py (select/eq/gte/lte/
    lt/gt/in_/is_/not_/ilike/order/limit) aplicando os filtros de fato
    sobre uma lista de dicts em memória — pra testar código que consulta o
    Supabase sem precisar de uma instância real. `execute()` devolve o
    resultado já filtrado."""

    def __init__(self, dados):
        self._dados = list(dados)

    def select(self, *_a, **_kw):
        return self

    def eq(self, campo, valor):
        return _FakeQuery([d for d in self._dados if d.get(campo) == valor])

    def neq(self, campo, valor):
        return _FakeQuery([d for d in self._dados if d.get(campo) != valor])

    def gte(self, campo, valor):
        return _FakeQuery([d for d in self._dados if d.get(campo) is not None and d[campo] >= valor])

    def lte(self, campo, valor):
        return _FakeQuery([d for d in self._dados if d.get(campo) is not None and d[campo] <= valor])

    def lt(self, campo, valor):
        return _FakeQuery([d for d in self._dados if d.get(campo) is not None and d[campo] < valor])

    def gt(self, campo, valor):
        return _FakeQuery([d for d in self._dados if d.get(campo) is not None and d[campo] > valor])

    def in_(self, campo, valores):
        conjunto = set(valores)
        return _FakeQuery([d for d in self._dados if d.get(campo) in conjunto])

    def is_(self, campo, valor):
        alvo = None if valor in ("null", None) else valor
        return _FakeQuery([d for d in self._dados if d.get(campo) is alvo])

    def ilike(self, campo, padrao):
        termo = str(padrao).strip("%").lower()
        return _FakeQuery([d for d in self._dados if termo in str(d.get(campo, "")).lower()])

    def order(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    @property
    def not_(self):
        return _FakeQueryNot(self)

    def execute(self):
        return SimpleNamespace(data=self._dados)


class FakeSupabaseClient:
    """Cliente Supabase fake pra testar código que consulta várias tabelas
    sem precisar de uma instância real. `dados_por_tabela` mapeia o nome
    da tabela pra lista de dicts — os filtros encadeados (eq/gte/lte/...)
    são aplicados de verdade sobre essa lista."""

    def __init__(self, dados_por_tabela: dict[str, list]):
        self._dados_por_tabela = dados_por_tabela

    def table(self, nome: str) -> _FakeQuery:
        return _FakeQuery(self._dados_por_tabela.get(nome, []))
