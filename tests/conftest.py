"""Fixtures compartilhadas entre os testes."""

import uuid
from types import SimpleNamespace


class _FakeQueryNot:
    """Suporta `.not_.is_(campo, "null")` -> campo IS NOT NULL."""

    def __init__(self, query: "_FakeQuery"):
        self._query = query

    def is_(self, campo, _valor):
        return self._query._nova([d for d in self._query._dados if d.get(campo) is not None])


class _FakeQuery:
    """Substitui a cadeia de métodos do postgrest-py (select/eq/gte/lte/
    lt/gt/in_/is_/not_/ilike/order/limit/insert/update/delete) sobre uma
    lista de dicts guardada, por referência, dentro do FakeSupabaseClient.

    Importante (igual ao supabase-py de verdade): `.update(valores)` e
    `.delete()` só REGISTRAM a intenção — a mutação real só acontece em
    `.execute()`, depois que todos os `.eq(...)` encadeados já filtraram
    quais linhas são o alvo. Fazer a mutação na hora de `.update()` (antes
    do filtro) atualizaria a tabela inteira por engano."""

    def __init__(self, dados_filtrados: list, tabelas: dict[str, list], nome: str, pendente: tuple[str, dict] | None = None):
        self._dados = list(dados_filtrados)
        self._tabelas = tabelas
        self._nome = nome
        self._pendente = pendente  # ("update", valores) | ("delete", {}) | None

    def _nova(self, dados_filtrados) -> "_FakeQuery":
        return _FakeQuery(dados_filtrados, self._tabelas, self._nome, self._pendente)

    def select(self, *_a, **_kw):
        return self

    def eq(self, campo, valor):
        return self._nova([d for d in self._dados if d.get(campo) == valor])

    def neq(self, campo, valor):
        return self._nova([d for d in self._dados if d.get(campo) != valor])

    def gte(self, campo, valor):
        return self._nova([d for d in self._dados if d.get(campo) is not None and d[campo] >= valor])

    def lte(self, campo, valor):
        return self._nova([d for d in self._dados if d.get(campo) is not None and d[campo] <= valor])

    def lt(self, campo, valor):
        return self._nova([d for d in self._dados if d.get(campo) is not None and d[campo] < valor])

    def gt(self, campo, valor):
        return self._nova([d for d in self._dados if d.get(campo) is not None and d[campo] > valor])

    def in_(self, campo, valores):
        conjunto = set(valores)
        return self._nova([d for d in self._dados if d.get(campo) in conjunto])

    def is_(self, campo, valor):
        alvo = None if valor in ("null", None) else valor
        return self._nova([d for d in self._dados if d.get(campo) is alvo])

    def ilike(self, campo, padrao):
        termo = str(padrao).strip("%").lower()
        return self._nova([d for d in self._dados if termo in str(d.get(campo, "")).lower()])

    def order(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    @property
    def not_(self):
        return _FakeQueryNot(self)

    def insert(self, registro_ou_lista):
        # insert não tem filtro pra esperar — aplica na hora e devolve os
        # registros inseridos (com id gerado, se não veio um).
        registros = registro_ou_lista if isinstance(registro_ou_lista, list) else [registro_ou_lista]
        tabela_real = self._tabelas.setdefault(self._nome, [])
        inseridos = []
        for r in registros:
            novo = dict(r)
            novo.setdefault("id", uuid.uuid4().hex)
            tabela_real.append(novo)
            inseridos.append(novo)
        return _FakeQuery(inseridos, self._tabelas, self._nome)

    def update(self, valores: dict) -> "_FakeQuery":
        return _FakeQuery(self._dados, self._tabelas, self._nome, pendente=("update", valores))

    def delete(self) -> "_FakeQuery":
        return _FakeQuery(self._dados, self._tabelas, self._nome, pendente=("delete", {}))

    def execute(self):
        if self._pendente is None:
            return SimpleNamespace(data=self._dados)

        acao, valores = self._pendente
        ids_alvo = {d["id"] for d in self._dados if "id" in d}
        tabela_real = self._tabelas.get(self._nome, [])
        if acao == "update":
            afetados = []
            for registro in tabela_real:
                if registro.get("id") in ids_alvo:
                    registro.update(valores)
                    afetados.append(registro)
            return SimpleNamespace(data=afetados)
        else:  # delete
            removidos = [r for r in tabela_real if r.get("id") in ids_alvo]
            self._tabelas[self._nome] = [r for r in tabela_real if r.get("id") not in ids_alvo]
            return SimpleNamespace(data=removidos)


class FakeSupabaseClient:
    """Cliente Supabase fake pra testar código que consulta e também
    escreve várias tabelas, sem precisar de uma instância real.
    `dados_por_tabela` mapeia o nome da tabela pra lista de dicts —
    filtros encadeados (eq/gte/lte/...) são aplicados de verdade sobre
    essa lista, e insert/update/delete mutam a tabela de verdade (visível
    em chamadas seguintes)."""

    def __init__(self, dados_por_tabela: dict[str, list]):
        self._tabelas = {nome: list(linhas) for nome, linhas in dados_por_tabela.items()}

    def table(self, nome: str) -> _FakeQuery:
        return _FakeQuery(self._tabelas.get(nome, []), self._tabelas, nome)
