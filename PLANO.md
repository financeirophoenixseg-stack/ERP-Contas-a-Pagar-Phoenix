# Plano do Projeto — ERP Contas a Pagar/Receber (Phoenix / Vizentim)

**Prazo:** 17/08/2026 → 28/09/2026 (6 semanas corridas)
**Hoje:** 26/08/2026 — dia 10, 32 dias corridos restantes
**Responsável:** financeiro@phoenixseg.com.br
**Equipe:** só o usuário + Claude

## Escopo ampliado (26/08) — contas a pagar/receber completo

Além da conciliação de comissões (escopo original), o sistema vira um **contas a
pagar/receber completo**:
- Todo lançamento bancário que não bate com uma comissão vira uma **divergência
  a classificar**: o usuário escolhe se é um **cliente** (recebimento) ou
  **fornecedor** (pagamento), podendo cadastrar um novo na hora.
- Cada lançamento é vinculado a uma conta do **plano de contas** (padrão para
  corretora de seguros, 35 contas: Ativo/Passivo/Patrimônio Líquido/Receita/
  Despesa — ver `seed_plano_contas.py`).
- O sistema **aprende**: ao classificar, salva um padrão de texto da descrição
  → próximos lançamentos parecidos já vêm com a classificação sugerida (tabela
  `regras_identificacao`, mesma ideia do "Litor OFX" antigo do usuário).
- **DRE e Balanço Patrimonial**: serão relatórios **calculados matematicamente**
  a partir do plano de contas classificado — não gerados livremente por IA. A
  IA entra só na sugestão de classificação (com o usuário sempre confirmando),
  nunca escrevendo os números da demonstração financeira diretamente — isso é
  uma decisão de integridade, para não arriscar relatório financeiro errado.
  Entram no cronograma como parte do dashboard da Semana 5.
- **Lançamentos previstos** (26/08, pedido do usuário): cadastro de despesa/
  receita ANTES de acontecer — avulsa, parcelada ou fixa/recorrente (tabela
  `lancamentos_previstos`, tela `Contas a Pagar e Receber`). Concilia sozinho
  quando o crédito/débito correspondente aparece no OFX; senão dá pra marcar
  como pago manualmente (ex.: pagamento em dinheiro).

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
| 4 | 07/09 – 13/09 | Motor de conciliação automática + divergências + auditoria + classificação de lançamentos (cliente/fornecedor + plano de contas) |
| 5 | 14/09 – 20/09 | Dashboard financeiro + pesquisa por cliente + alertas + DRE e Balanço Patrimonial (calculados a partir do plano de contas) |
| 6 | 21/09 – 28/09 | Testes com arquivos reais, correções, segurança, backup, preparação para uso |

Meta intermediária: sistema navegável importando os OFX reais já na semana 2; caso Suhai (R$ 1.013,05 bruto → R$ 977,59 líquido → conciliado) funcionando ponta a ponta na semana 3.

## Decisão de stack (25/08/2026)

- **Frontend/app:** Streamlit (Python) — já usado pelo usuário nesta máquina (`~/.streamlit`).
- **Banco de dados:** Supabase (Postgres gerenciado) — já usado pelo usuário nesta máquina (`~/.supabase`).
- **Parsing:** Python (`ofxparse`/parsing manual de OFX, `pdfplumber` para os PDFs de demonstrativo).
- Repositório local: `Documents/ERP-Phoenix-Vizentim`, git iniciado nesta pasta.

## Status

- ✅ 25/08 — Pasta e repositório criados, plano e cronograma documentados, stack decidida.
- ✅ 25/08 — Schema do banco (Supabase) criado em `schema.sql`; repositório publicado no GitHub (`ERP-Contas-a-Pagar-Phoenix`, privado) com rotina semanal de check-in.
- ✅ 26/08 — Cadastro de Empresas e Contas Bancárias (Streamlit) funcionando.
- ✅ 26/08 — Importador de OFX: parser Python portado da lógica já validada em `Litor OFX - Atualizado/src/app.js` (regex por tag, fallback de encoding windows-1252, dedup por FITID), 4 testes automatizados passando incluindo o caso de referência real (Suhai, 21/07/2026, R$ 977,59, conta 4928-0). Tela de importação identifica a empresa pela conta cadastrada e bloqueia contas não cadastradas.
- ✅ 26/08 — Supabase conectado de verdade (`.env` configurado, RLS desativada por ser app interno sem login ainda). Empresas Phoenix e Vizentim cadastradas, com as contas bancárias reais (756/4406-7/4928-0 → Vizentim, 756/4406-7/4930-1 → Phoenix).
- ✅ 26/08 — Importador do demonstrativo Suhai (PDF): parser (`suhai_parser.py`) extrai corretor/CNPJ, data, valores brutos/líquidos/impostos e cada linha de comissão; identifica a empresa pelo CNPJ; cria clientes automaticamente; 10 testes unitários passando.
- ✅ 26/08 — Motor de conciliação (v1) funcionando nos dois sentidos (Suhai→OFX e OFX→Suhai), incluindo alerta de auditoria quando o crédito aparece na conta de outra empresa. **Validado ponta a ponta contra o banco real com o caso de referência**: demonstrativo Suhai de 21/07/2026 (15 comissões, 13 clientes criados automaticamente, líquido R$ 977,59) conciliado automaticamente com o crédito Pix "SUHAI SEGURADORA" na conta 4928-0 (Vizentim) do mesmo dia — mesmo caso descrito na fase de planejamento do projeto.
- ✅ 26/08 — Escopo ampliado para contas a pagar/receber completo (ver seção acima). Plano de contas padrão (35 contas) criado e populado no Supabase real (`seed_plano_contas.py`). Tabelas `fornecedores` e `regras_identificacao` criadas (`migrations/002_plano_contas_fornecedores.sql`).
- ✅ 26/08 — Tela "Classificar Lançamentos": lista transações bancárias não conciliadas com nenhuma comissão, permite cadastrar cliente/fornecedor na hora, vincular à conta do plano de contas, e salva um padrão de identificação para sugerir automaticamente em lançamentos futuros parecidos. Lógica de sugestão (`regras_identificacao.py`) com testes automatizados; fluxo de gravação validado contra o Supabase real (criado e depois limpo um lançamento de teste, dados fictícios não ficaram no banco).
- ✅ 26/08 — Importador generalizado para múltiplas seguradoras: parser da Suhai movido para `parsers/suhai.py` com interface comum (`parsers/base.py`) e registro central (`parsers/__init__.py`); tela `Importar Comissão` agora tem seletor de seguradora. Adicionar a próxima seguradora passa a ser só escrever e registrar um novo `parsers/<nome>.py`.
- ✅ 26/08 — Importador da **Bradesco Saúde** (PDF + planilha) construído e validado contra arquivos reais do usuário (fatura 15163838, apólice 1117397/1: soma de 17 linhas de beneficiários bate exatamente com os R$ 277,00 do resumo). Layout bem diferente da Suhai: não traz nome de cliente, só beneficiários agrupados por apólice — criada a tabela `apolice_clientes` para esse mapeamento (primeira vez o usuário associa manualmente, depois reconhece sozinho, mesma ideia das `regras_identificacao`). 11 novos testes (25 no total).
- ✅ 26/08 — Tela `Importar Comissão` não pede mais para escolher a seguradora: detecta sozinha pelo layout (PDF e/ou planilha).
- ✅ 26/08 — PDF e planilha da Bradesco Saúde viram fontes independentes (o usuário nem sempre tem os dois) — parser aceita qualquer combinação, extraindo os detalhes direto da tabela do PDF quando não há planilha. Corrigido bug de normalização do número de apólice (formato diferente em cada arquivo). Validado nas 3 combinações contra os arquivos reais.
- ✅ 26/08 — **Primeira importação real da Bradesco Saúde feita pelo usuário**: apólice 1117397/1 → cliente real "Romar Indústria e Comércio de Materiais Hidr[áulicos]" (Vizentim), R$ 277,00. Um bug real apareceu no processo (RLS ainda ativa em `apolice_clientes` travou a confirmação no meio, e havia um bug separado: escolher um cliente já existente para uma apólice nova não salvava o mapeamento, só "+ Novo cliente" salvava) — ambos corrigidos; dados incompletos dessa tentativa foram completados manualmente sem duplicar nada. Adicionada reversão automática: se a confirmação falhar no meio do caminho, desfaz o lote parcial em vez de travar novas tentativas.
- ✅ 26/08 — Módulo de **lançamentos previstos** (contas a pagar/receber avulsas, parceladas e fixas) construído e validado contra o Supabase real. Motor de conciliação do OFX estendido para também tentar bater com esses lançamentos previstos, além dos lotes de comissão.
