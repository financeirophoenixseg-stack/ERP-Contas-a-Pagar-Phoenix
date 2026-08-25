# Plano do Projeto — ERP Conciliação Bancária + Comissões (Phoenix / Vizentim)

**Prazo:** 17/08/2026 → 28/09/2026 (6 semanas corridas)
**Hoje:** 25/08/2026 — dia 9, 33 dias corridos restantes
**Responsável:** financeiro@phoenixseg.com.br
**Equipe:** só o usuário + Claude

> Projeto independente do `Phoenix-Web-Multiusuario-MVP-v5.12` (sistema de conferência de faturamento de plano de saúde). Não misturar prazos, dados ou decisões entre os dois.

## Escopo do negócio

Conciliação automática entre extratos bancários (OFX) e demonstrativos de comissão de corretagem (seguradoras), para as empresas do grupo **Phoenix** e **Vizentim**.

### Estrutura de dados definida

```
EMPRESAS DO GRUPO (Phoenix, Vizentim, ...)
  └── Contas bancárias (banco + agência + conta) — identifica empresa automaticamente no OFX

CLIENTES (cadastro mestre, independente de empresa)
  └── NEGÓCIOS / CONTRATOS
        ├── Empresa responsável (Phoenix, Vizentim, ...)
        ├── Seguradora
        └── Comissões
              └── MOVIMENTAÇÕES DE COMISSÃO (razão, não só valor final)
                    + Pagamento de comissão
                    + Adiantamento
                    - Cancelamento
                    - Recuperação de comissão
                    + Ajuste
                    - Estorno
```

- Cliente e empresa do grupo **não são a mesma entidade** — um cliente pode ter negócios com mais de uma empresa no futuro. Na v1 (sem módulo de Contratos ainda), manter uma "empresa principal" no cadastro do cliente como atalho.
- Guardar sempre **comissão bruta** e **valor líquido recebido no banco** separados (impostos/retenções variam por lote) — evita falso alarme de divergência.
- Regra de auditoria: se uma comissão de cliente vinculado à Phoenix aparecer em conta bancária da Vizentim (ou vice-versa), gerar alerta em vez de aceitar automaticamente.

### Casos de referência (mapeamento confirmado)

| Conta | Banco/Agência | Empresa |
|---|---|---|
| 4928-0 | 756 / 4406-7 | Vizentim |
| 4930-1 | 756 / 4406-7 | Phoenix |

Caso de teste nº 1 (validado manualmente): demonstrativo Suhai, pagamento 21/07/2026, líquido R$ 977,59 → crédito Pix "SUHAI SEGURADORA" na conta 4928-0 (Vizentim) no mesmo dia → match exato.

### Algoritmo do motor de conciliação (v1, seguradora Suhai)

1. Ler OFX → identificar conta → resolver empresa (via cadastro de contas bancárias)
2. Encontrar crédito na data/valor esperado, ler descrição
3. Ler demonstrativo da seguradora (PDF) → extrair corretor, data de pagamento, valor líquido, linhas de comissão por cliente/apólice
4. Comparar: empresa ✓, seguradora ✓, data ✓, valor líquido ✓ → confiança ~100% → conciliar automático
5. Criar clientes que não existem ainda a partir das linhas do demonstrativo
6. Criar movimentações de comissão (uma por linha, incluindo cancelamentos/recuperações negativas)
7. Vincular lote ao recebimento bancário

Importante: começar com **um** layout de seguradora (Suhai) funcionando bem de ponta a ponta antes de generalizar para outras (Bradesco, etc.) — não tentar ensinar todas de uma vez.

## Definição de "MVP lançado"

Usuário entra no sistema, escolhe Phoenix / Vizentim / consolidado, importa OFX + demonstrativos de comissão, e o sistema:
- identifica automaticamente conta → empresa;
- lê movimentações bancárias e evita importação duplicada;
- lê demonstrativo de comissão (Suhai primeiro), cria clientes automaticamente quando necessário;
- registra apólice, parcela, comissão bruta, impostos/retenções, líquido;
- concilia automaticamente quando a confiança é alta; mostra divergências para revisão manual;
- permite pesquisar cliente e ver histórico de movimentações de comissão;
- mantém arquivo de origem + trilha de auditoria;
- mostra dashboard com status de conciliação;
- emite alertas (ex.: comissão de cliente de uma empresa aparecendo na conta bancária de outra).

## Cronograma (6 semanas, 17/08 → 28/09/2026)

| Semana | Período | Entrega |
|---|---|---|
| 1 | 17/08 – 23/08 | Arquitetura, banco de dados (Supabase), multiempresa, usuários, estrutura base do financeiro |
| 2 | 24/08 – 30/08 | Importador OFX + identificação automática Phoenix/Vizentim por conta + prevenção de duplicidade |
| 3 | 31/08 – 06/09 | Importador Suhai (PDF) + criação automática de clientes + lotes/comissões/estornos/impostos |
| 4 | 07/09 – 13/09 | Motor de conciliação automática + divergências + auditoria |
| 5 | 14/09 – 20/09 | Dashboard financeiro + pesquisa por cliente + alertas |
| 6 | 21/09 – 28/09 | Testes com arquivos reais, correções, segurança, backup, preparação para uso |

Meta intermediária: sistema navegável importando os OFX reais já na semana 2; caso Suhai (R$ 1.013,05 bruto → R$ 977,59 líquido → conciliado) funcionando ponta a ponta na semana 3.

## Decisão de stack (25/08/2026)

- **Frontend/app:** Streamlit (Python) — já usado pelo usuário nesta máquina (`~/.streamlit`).
- **Banco de dados:** Supabase (Postgres gerenciado) — já usado pelo usuário nesta máquina (`~/.supabase`).
- **Parsing:** Python (`ofxparse`/parsing manual de OFX, `pdfplumber` para os PDFs de demonstrativo).
- Repositório local: `Documents/ERP-Phoenix-Vizentim`, git iniciado nesta pasta.

## Status

- ✅ 25/08 — Pasta e repositório criados, plano e cronograma documentados, stack decidida.
- Próximo passo: modelo de dados (schema Supabase) para empresas, contas bancárias, clientes, negócios, seguradoras, lotes e movimentações de comissão.
