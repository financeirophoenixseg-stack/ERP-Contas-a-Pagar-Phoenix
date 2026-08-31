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
- ✅ 26/08 — **Semana 5 concluída**: Dashboard (totais a pagar/receber, comissões por status, alertas), Pesquisa por Cliente (histórico completo), Alertas (auditoria + vencidos), DRE e Balanço Patrimonial (calculados, não gerados por IA). Bug de contabilidade corrigido durante a validação: impostos retidos por lote agora entram como despesa tributária no DRE (senão a receita de comissões ficava inflada pelo valor bruto). Resultado do período validado batendo exato com os lotes reais (R$ 1.254,59).
- ✅ 26/08 — Revisão de segurança feita (agente especializado): corrigido path traversal real no upload de arquivos (nome do upload não é confiável) e um `except` genérico demais que escondia erros reais na importação de OFX. Sem outros achados além do RLS desativado (já era decisão conhecida).
- ✅ 26/08 — **Terceira seguradora: Porto Seguro** (PDF e/ou HTML `.do`, cada um sozinho suficiente). Identifica a empresa por código **SUSEP** (não CNPJ) — `57557J` = Phoenix, confirmado e salvo. Validado contra os 4 arquivos reais do usuário (2 layouts × 2 formatos): totais batendo exato (R$ 785,51 e R$ 6.302,32/6.398,29), sem colisão de detecção com Suhai/Bradesco. Lote real da Porto Saúde (8 clientes, R$ 6.302,32) já importado no Supabase.
- ✅ 26/08 — **Classificação agenciamento x vitalício** (saúde/vida): regra por cliente (quantas primeiras parcelas são agenciamento) provisiona receita futura esperada quando detecta comissão vitalícia (recorrente, sem fim definido). Validado contra o Supabase real (6 provisões mensais geradas, reimportação atualiza sem duplicar).
- ✅ 26/08 — **Parcelamento auto/RE**: regra por apólice (nº total de parcelas conhecido) provisiona as parcelas restantes com fim certo. Mesmo mecanismo do vitalício, mas finito.
- ✅ 26/08 — **Regra real de comissão da Suhai** implementada a partir da planilha de cálculo que o usuário usa ("Novo Suhai", 73%): `parcelas_enquadradas = INT(0.73 ÷ percentual)` — permite prever quantas parcelas futuras uma apólice da Suhai vai receber comissão só pelo percentual já informado no próprio demonstrativo, sem cadastro manual. Só se aplica a linhas "pagamento" (comissão de vigência) — adiantamento/cancelamento/recuperação não seguem essa fórmula (confirmado contra as 15 linhas reais do demonstrativo de referência).
- ✅ 27/08 — Tela **Configurações**: cadastro direto de Clientes, Fornecedores e Plano de Contas (antes só dava pra criar de dentro de outro fluxo).
- ✅ 27/08 — **Backup** (item da Semana 6): script exporta todas as tabelas do Supabase para JSON local (`backup.py` / `fazer_backup.bat`), validado contra o banco real (16 tabelas).
- ⚠️ 27/08 — **Usuário trocou de computador** (o antigo estava travando muito). Projeto clonado do GitHub para `OneDrive\Documentos\Projetos IA\ERP-Phoenix-Vizentim-novo`. Esta sessão do Claude Code continua rodando na máquina antiga — sincronização segue via GitHub (push daqui, `git pull` lá). `.venv` recriado do zero na máquina nova (não é portátil); `.env` copiado manualmente.
- ✅ 27/08 — **Consolidação em Configurações** (princípio definido pelo usuário: tudo que configura o sistema fica numa tela só, em abas): Empresas, Contas Bancárias, Regras de Comissão, Regras de Identificação e Apólice→Cliente todas migradas pra lá; páginas separadas removidas. 8 abas ao todo.
- ✅ 27/08 — **Conciliação por fornecedor** para despesas/receitas fixas de valor variável (ex.: conta de luz): reconhece o fornecedor pela descrição já ensinada e casa com a previsão do mesmo mês mesmo com valor diferente — atualiza o valor real e propaga pras próximas parcelas já provisionadas da mesma recorrência. Validado contra o Supabase real.
- ✅ 27/08 — **Relatório de Contas Atrasadas** (em Alertas): separado A Pagar/A Receber, com dias de atraso e totais.
- ✅ 27/08 — **Quarta seguradora: Hapvida/NDI** (CSV + HTML). Bug real corrigido durante a validação: coluna "VL COMISSÃO" (total do lote, com acento) colidia com "VL COMISSAO" (valor da linha, sem acento) no normalizador de nomes de coluna, inflando o total em ~1200x — corrigido priorizando correspondência exata antes da comparação sem acento. Validado contra os arquivos reais (R$ 6.814,57).
- ✅ 27/08 — **Anexos** (boletos/comprovantes): tela nova (`pages/12_Anexos.py`) guarda os arquivos no Supabase Storage (bucket `anexos`), organizados por ano/mês/tipo, com vínculo opcional a um lançamento previsto, listagem/filtro/download/exclusão. Leitura automática da linha digitável do boleto fica pendente — aguardando o usuário enviar um boleto real para validar o formato antes de implementar (não adivinhar).
- ✅ 27/08 — **Sincronização automática com o SharePoint da empresa**: cada anexo salvo no sistema agora envia uma cópia automaticamente para a biblioteca de documentos do site `Phoenix-DocumentosCorporativos` no SharePoint (`sharepoint.py`), mantendo a mesma estrutura de pastas (ano/mês/tipo) do Supabase Storage. Exclusão de um anexo remove também a cópia no SharePoint. Autenticação via app registrado no Entra ID (client credentials, permissão de aplicativo `Sites.Selected`) — a concessão de acesso a esse site específico foi feita uma única vez via Microsoft Graph com um token delegado de administrador (fluxo interativo de login por código, feito pelo próprio Claude Code por script, já que o Graph Explorer se mostrou difícil de operar manualmente). Testado ponta a ponta contra o SharePoint real: upload, URL retornada e exclusão confirmados.
- ✅ 27/08 — **Anexos movidos para dentro de Contas a Pagar e Receber** (a pedido do usuário — antes era uma aba separada "Anexos"): cada lançamento tem sua própria seção de anexos (anexar/ver/baixar/apagar), dá pra anexar já na hora de criar o lançamento, e existe uma lista global de todos os anexos no fim da página. Página separada `12_Anexos.py` removida.
- ✅ 27/08 — **Leitura automática de boleto/guia via IA** (`leitor_boleto.py`): usuário mandou um exemplo real (Guia FGTS Digital) e descobrimos que boletos/guias não têm layout fixo — muitos PDFs desse tipo vêm com o texto interno embaralhado (fonte incorporada sem mapeamento), impossível de extrair pelo método usado nos parsers de comissão. Decidido com o usuário: em vez de escrever um parser por formato (inviável, formatos variam demais), o PDF é mandado direto pra IA (Claude, com visão) interpretar e devolver valor/vencimento/descrição/favorecido sugeridos em JSON — **o usuário sempre confere e confirma antes de qualquer lançamento ser criado**, preservando a regra de nunca deixar a IA decidir um valor financeiro sozinha. Integrado em Contas a Pagar e Receber: sobe o PDF, confere os campos, confirma, e o lançamento + anexo já saem vinculados. Precisa de `ANTHROPIC_API_KEY` no `.env` (usuário está criando a conta/chave). Testado com mock (JSON válido/inválido, ausência de campo) — 4 novos testes (70 no total). Pendente: validar contra a leitura real assim que a chave estiver configurada.
- ✅ 27/08 — **Leitura de boleto validada contra arquivo real**: usuário criou a chave da Anthropic (teve que ser uma chave de dentro de um Workspace específico, não a "identity-linked" da conta pessoal — essa dava erro pedindo `anthropic-workspace-id`). Testado contra a Guia FGTS Digital real: valor (R$ 1.578,01), vencimento (18/09/2026) e descrição extraídos exatos, e a IA sinalizou sozinha, com confiança "média", que o CNPJ do empregador aparecia truncado no documento — sem inventar o restante.
- ✅ 27/08 — **Revisão de segurança do código novo** (SharePoint, Anexos em Contas a Pagar/Receber, leitura de boleto): achado real — nome do arquivo enviado pelo usuário sendo usado sem sanitização para montar o caminho de armazenamento (mesma classe de bug já corrigida uma vez na importação de comissão), o que permitia, em tese, escapar da pasta de anexos e sobrescrever outro arquivo na biblioteca do SharePoint. Corrigido nos 3 pontos (`Path(nome).name`) + validação defensiva extra dentro de `sharepoint.py` (recusa qualquer segmento `..`/vazio antes de montar a URL do Graph). 4 novos testes (74 no total).
- ✅ 31/08 — **Revisão de ponta a ponta de todas as telas** (Dashboard, Importar OFX, Importar Comissão, Classificar Lançamentos, Contas a Pagar e Receber, Pesquisa Cliente, Alertas, DRE e Balanço, Configurações): navegado e conferido contra o Supabase real, sem erros de console/execução em nenhuma. Achado e corrigido um bug real: todo valor em R$ aparecia em formato americano (`R$ 1,000.00`, vírgula como milhar) em vez do formato brasileiro (`R$ 1.000,00`) — criado `formatacao.py` (`moeda()`) e aplicado em todas as telas que exibem valores (Dashboard, Alertas, DRE/Balanço, Pesquisa Cliente, Contas a Pagar/Receber, Importar Comissão, Classificar Lançamentos). 3 novos testes (77 no total).
- ✅ 31/08 — **Datas em formato brasileiro + prévia de valor formatado** (pedido do usuário, com print da tela): todo `st.date_input` do sistema agora usa `format="DD/MM/YYYY"` (antes mostrava AAAA/MM/DD); toda data vinda do Supabase em formato ISO (dataframes, seletores, rótulos) passa por `data_br()` antes de aparecer na tela. Como o campo de valor não pode ter "R$"/ponto de milhar dentro dele sem quebrar os botões +/- do navegador, foi adicionada uma legenda logo abaixo de cada campo de valor mostrando o total formatado em tempo real (ex.: digitar `2345.67` mostra "R$ 2.345,67" embaixo). Cuidado tomado em `Importar OFX`: a tabela de prévia também alimenta a lógica de conciliação (comparações numéricas, insert no banco) — os campos usados pra cálculo continuam com o valor/data crus, só a cópia exibida em tela é formatada. 4 novos testes pro `data_br()` (81 no total).
- ✅ 31/08 — **Campo de valor trocado de numérico pra texto livre** (usuário reportou o campo numérico nativo do navegador misturando dígitos digitados com o conteúdo antigo, ex.: digitar "1000" virava "0,0011000"). Criado `parse_valor()` em `formatacao.py` — aceita tanto o formato brasileiro completo ("1.000,50") quanto digitação simples sem separador de milhar ("1000.5" ou "1000") — e `_campo_valor()` em Contas a Pagar e Receber, um campo de texto que mostra o valor interpretado formatado logo abaixo, sem herdar conteúdo antigo. Aplicado nos 4 campos de valor da tela (avulso, parcelado, fixo, boleto por IA). 7 novos testes (87 no total).
- ✅ 31/08 — **Baixa automática por comprovante** (pedido do usuário): tela nova em Contas a Pagar e Receber pra subir vários comprovantes de pagamento de uma vez — cada um é lido pela IA (`leitor_comprovante.py`) e casado com um lançamento previsto por valor + proximidade de data (±3 dias, tolerância de R$0,01, mesma lógica de tolerância já usada na conciliação do OFX). Quando o casamento é inequívoco (exatamente 1 candidato) e a leitura teve confiança razoável, o anexo é vinculado e o lançamento marcado como pago sozinho; quando fica ambíguo (0 ou 2+ candidatos) ou a leitura é de baixa confiança, o comprovante é só salvo sem vínculo, para revisão manual — nunca decide uma baixa incerta sozinho. Extraído `leitor_ia.py` como base compartilhada entre `leitor_boleto.py` e `leitor_comprovante.py` (mesmo mecanismo de chamar a IA com o PDF e parsear JSON). Corrigido de quebra um bug real descoberto na validação: a IA às vezes envolve a resposta num bloco markdown (\`\`\`json), quebrando o parser — corrigido removendo a cerca antes de parsear (afetava também o leitor de boleto já em produção). Validado contra o Supabase real (matching correto e recusa de matching quando o valor não bate) e contra a API real. 18 novos testes (98 no total).
- ✅ 31/08 — **Primeiro teste real da baixa por comprovante, feito pelo usuário**: 2 comprovantes Pix do Sicoob enviados de uma vez — 1 casou sozinho (valor + data bateram com exatamente 1 lançamento) e já saiu vinculado e marcado como pago; o outro ficou ambíguo e foi salvo sem vínculo, como esperado. Faltava uma forma de vincular esse manualmente depois — adicionado em "Todos os anexos": cada anexo sem vínculo agora tem um seletor de lançamento + checkbox "marcar pago" + botão "Vincular". Testado contra os dados reais gerados pelo próprio usuário.
- ✅ 31/08 — **2 ajustes reais encontrados no teste do usuário com comprovantes**: (1) margem de data pra casar comprovante com lançamento era de só ±3 dias — um pagamento real 4 dias após o vencimento ficou de fora; alargada pra ±7 dias (empresa costuma pagar em lote, não sempre no dia exato). (2) reenviar o mesmo comprovante criava um anexo duplicado — adicionado hash do arquivo (`hash_arquivo`, migração `010_anexos_hash.sql`) em todos os pontos de upload de anexo da tela, com verificação de duplicidade antes de processar no upload em lote (mesma ideia já usada em `ofx_importacoes`/`lotes_comissao`). 1 novo teste (99 no total).
- ✅ 31/08 — **Desempate quando há mais de um candidato pro comprovante** (pergunta do usuário: "e se eu tiver 2 pagamentos de R$500?"): antes, qualquer ambiguidade (2+ candidatos) já desistia e deixava sem vínculo. Agora tenta desempatar, só decidindo se cada critério reduzir a exatamente um: (1) vencimento exatamente igual à data do pagamento; (2) nome do fornecedor/cliente do lançamento bate com o "favorecido" que a IA leu no comprovante. Se ainda sobrar mais de um depois dos dois critérios, continua sem decidir sozinho. 4 novos testes (102 no total). Também limpos manualmente 8 anexos duplicados de teste no Supabase (sobras de antes da deduplicação por hash existir).
- ✅ 31/08 — **Estrutura pra integração bancária (Open Finance) preparada** (usuário perguntou se dava pra conectar direto com o banco — usa Sicoob, Bradesco e C6, os 3 participam do Open Finance Brasil obrigatoriamente). Virar participante direto do Open Finance é inviável pra uma corretora pequena (certificado próprio, homologação) — caminho real é via agregador certificado. Escolhida a **Pluggy** (cobre os 3 bancos). Como o usuário ainda não tem conta lá, preparei a estrutura pra ativar depois, sem decidir nada por ele: `pluggy_integration.py` (cliente da API: autenticação, connect token, listar contas/transações), migração `011_integracoes_bancarias.sql` (liga cada conta bancária nossa à conexão do Pluggy), e aba nova **"Integração Bancária"** em Configurações — mostra instruções de ativação se não configurado, ou o fluxo de conectar (widget Pluggy Connect embutido) se já tiver a chave. ⚠️ Só a parte de API REST (autenticação/contas/transações) segue a documentação oficial da Pluggy com confiança razoável; o encaixe fino do widget JS (Pluggy Connect) ainda não foi validado contra uma conta real — precisa ser conferido na primeira conexão de verdade. Ainda não alimenta o motor de conciliação automaticamente (isso é o próximo passo, depois de validar a conexão). 9 novos testes (109 no total).
- **Semana 6 — status:** segurança ✅, backup ✅, anexos + SharePoint ✅, leitura de boleto por IA ✅ (validada contra arquivo real), baixa automática por comprovante ✅ (testada pelo usuário com arquivos reais, com desempate de ambiguidade), revisão de ponta a ponta ✅, datas/valores em formato brasileiro ✅, estrutura de integração bancária preparada (Pluggy, pendente conta real do usuário pra validar). Restam: mais testes com arquivos reais (depende do usuário enviar mais demonstrativos) e preparação final para uso.
