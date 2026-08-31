-- Schema inicial — ERP Phoenix/Vizentim (Conciliação Bancária + Comissões)
-- Rodar no SQL editor do Supabase.

create table empresas (
    id uuid primary key default gen_random_uuid(),
    nome text not null unique,          -- 'Phoenix', 'Vizentim', ...
    cnpj text unique,                    -- CNPJ do corretor, usado para reconhecer a empresa em demonstrativos de comissão
    susep text unique,                   -- código SUSEP do corretor, idem para seguradoras que identificam por SUSEP (ex.: Porto Seguro)
    codigo_comissionado text unique,     -- código de comissionado/concessionária (ex.: Hapvida, '08LH')
    created_at timestamptz not null default now()
);

create table contas_bancarias (
    id uuid primary key default gen_random_uuid(),
    empresa_id uuid not null references empresas(id),
    banco text not null,                -- ex: '756'
    agencia text not null,               -- ex: '4406-7'
    conta text not null,                 -- ex: '4928-0'
    created_at timestamptz not null default now(),
    unique (banco, agencia, conta)
);

create table clientes (
    id uuid primary key default gen_random_uuid(),
    nome text not null,
    documento text,                      -- CPF/CNPJ, quando disponível
    empresa_principal_id uuid references empresas(id), -- atalho v1; futuro: negocios/contratos
    created_at timestamptz not null default now()
);

create table apolice_clientes (
    id uuid primary key default gen_random_uuid(),
    apolice text not null unique,        -- ex: '1117397/1' — número de apólice/subfatura
    cliente_id uuid not null references clientes(id),
    created_at timestamptz not null default now()
);

create table seguradoras (
    id uuid primary key default gen_random_uuid(),
    nome text not null unique             -- 'Suhai', 'Bradesco', ...
);

-- v1: sem tabela de contratos ainda (empresa_principal_id no cliente resolve isso).
-- Futuro: tabela negocios (cliente_id, empresa_id, seguradora_id) para clientes com múltiplos negócios.

create table ofx_importacoes (
    id uuid primary key default gen_random_uuid(),
    conta_bancaria_id uuid not null references contas_bancarias(id),
    arquivo_nome text not null,
    hash_arquivo text not null unique,    -- previne reimportação do mesmo arquivo
    importado_em timestamptz not null default now()
);

create table fornecedores (
    id uuid primary key default gen_random_uuid(),
    nome text not null,
    documento text,                      -- CPF/CNPJ, quando disponível
    created_at timestamptz not null default now()
);

create table plano_contas (
    id uuid primary key default gen_random_uuid(),
    codigo text not null unique,          -- ex: '4.1.1'
    nome text not null,
    tipo text not null,                   -- 'ativo' | 'passivo' | 'patrimonio_liquido' | 'receita' | 'despesa'
    conta_pai_id uuid references plano_contas(id),
    created_at timestamptz not null default now()
);

create table ofx_transacoes (
    id uuid primary key default gen_random_uuid(),
    ofx_importacao_id uuid not null references ofx_importacoes(id),
    conta_bancaria_id uuid not null references contas_bancarias(id),
    fit_id text,                          -- identificador único da transação no OFX (evita duplicidade)
    data date not null,
    valor numeric(14,2) not null,
    descricao text,
    conciliado boolean not null default false,
    -- Classificação contábil (contas a pagar/receber além da conciliação de comissão):
    cliente_id uuid references clientes(id),
    fornecedor_id uuid references fornecedores(id),
    plano_conta_id uuid references plano_contas(id),
    created_at timestamptz not null default now(),
    unique (conta_bancaria_id, fit_id)
);

-- Aprendizado: padrão de texto na descrição do OFX -> classificação sugerida,
-- para que lançamentos parecidos futuros sejam identificados automaticamente
-- (mesma ideia do "Litor OFX" antigo, agora persistida no banco).
create table regras_identificacao (
    id uuid primary key default gen_random_uuid(),
    padrao_descricao text not null,       -- substring, comparado em minúsculas
    cliente_id uuid references clientes(id),
    fornecedor_id uuid references fornecedores(id),
    plano_conta_id uuid references plano_contas(id),
    created_at timestamptz not null default now()
);

create table lotes_comissao (
    id uuid primary key default gen_random_uuid(),
    seguradora_id uuid not null references seguradoras(id),
    empresa_id uuid not null references empresas(id),
    arquivo_origem text not null,
    hash_arquivo text not null unique,    -- previne reimportação
    data_pagamento date not null,
    valor_bruto numeric(14,2),
    valor_irrf numeric(14,2),
    valor_iss numeric(14,2),
    valor_inss numeric(14,2),
    valor_pis_cofins_csll numeric(14,2),
    valor_liquido numeric(14,2) not null,
    ofx_transacao_id uuid references ofx_transacoes(id), -- preenchido quando conciliado
    status text not null default 'pendente', -- 'pendente' | 'conciliado' | 'divergente'
    created_at timestamptz not null default now()
);

create table movimentacoes_comissao (
    id uuid primary key default gen_random_uuid(),
    lote_id uuid not null references lotes_comissao(id),
    cliente_id uuid not null references clientes(id),
    tipo text not null,                   -- 'pagamento' | 'adiantamento' | 'cancelamento' | 'recuperacao' | 'ajuste' | 'estorno'
    apolice text,
    parcela text,
    percentual_comissao numeric(5,2),
    valor_parcela numeric(14,2),
    valor_comissao numeric(14,2) not null, -- pode ser negativo (cancelamento/recuperação/estorno)
    categoria text,                        -- 'agenciamento' | 'vitalicio' | null (sem regra de classificação cadastrada pro cliente)
    created_at timestamptz not null default now()
);

-- Regra de classificação agenciamento x vitalício por cliente (saúde/vida):
-- as primeiras `parcelas_agenciamento` parcelas de uma apólice são
-- agenciamento (comissão de entrada, % alto); da parcela seguinte em
-- diante é vitalícia (comissão recorrente, % baixo, dura enquanto a
-- apólice estiver ativa). Percentuais são só para referência/conferência
-- (a classificação de fato usa o nº da parcela, mais confiável que
-- comparar percentual, que varia por contrato).
-- Regra de parcelamento por apólice (auto/RE): número total de parcelas
-- esperadas. Ao chegar uma comissão da parcela P, se P < total, provisiona
-- as parcelas restantes (P+1 até total) como receita futura, usando o
-- valor observado como estimativa. Diferente da vitalícia: aqui a
-- provisão TERMINA quando total_parcelas é atingido.
create table regras_parcelamento (
    id uuid primary key default gen_random_uuid(),
    apolice text not null unique,
    cliente_id uuid references clientes(id),
    total_parcelas int not null,
    created_at timestamptz not null default now()
);

create table regras_classificacao_comissao (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null unique references clientes(id),
    parcelas_agenciamento int not null default 0,
    percentual_agenciamento numeric(5,2),
    percentual_vitalicio numeric(5,2),
    meses_provisionar int not null default 24, -- quantos meses à frente provisionar quando detectar vitalício (saúde ~24, vida pode passar de 100)
    created_at timestamptz not null default now()
);

create table auditoria_alertas (
    id uuid primary key default gen_random_uuid(),
    tipo text not null,                    -- ex: 'empresa_divergente'
    descricao text not null,
    lote_id uuid references lotes_comissao(id),
    cliente_id uuid references clientes(id),
    resolvido boolean not null default false,
    created_at timestamptz not null default now()
);

-- Contas a pagar/receber PREVISTAS: diferente de ofx_transacoes (o que já
-- aconteceu no banco) e de lotes_comissao (comissão já recebida), esta
-- tabela é o lançamento planejado ANTES de acontecer — avulso, parcelado
-- (várias linhas com o mesmo grupo_id) ou fixo/recorrente (idem). Quando o
-- OFX correspondente chega, o motor de conciliação marca como 'pago' e
-- vincula ofx_transacao_id, do mesmo jeito que já faz com lotes_comissao.
create table lancamentos_previstos (
    id uuid primary key default gen_random_uuid(),
    empresa_id uuid not null references empresas(id),
    tipo text not null,                    -- 'pagar' | 'receber'
    descricao text not null,
    valor numeric(14,2) not null,
    data_vencimento date not null,
    status text not null default 'previsto', -- 'previsto' | 'pago' | 'atrasado' | 'cancelado'
    data_pagamento date,
    cliente_id uuid references clientes(id),
    fornecedor_id uuid references fornecedores(id),
    plano_conta_id uuid references plano_contas(id),
    conta_bancaria_id uuid references contas_bancarias(id),
    ofx_transacao_id uuid references ofx_transacoes(id),
    grupo_id uuid,                          -- liga parcelas/recorrências do mesmo lançamento
    parcela_atual int,
    parcela_total int,
    recorrente boolean not null default false,
    apolice text,                           -- preenchido quando a provisão vem de comissão vitalícia (liga à apólice de origem, evita duplicar ao reimportar)
    created_at timestamptz not null default now()
);

-- Anexos: boletos e comprovantes guardados no Supabase Storage (bucket
-- "anexos"), ligados a um lançamento previsto e/ou a uma transação OFX.
create table anexos (
    id uuid primary key default gen_random_uuid(),
    lancamento_previsto_id uuid references lancamentos_previstos(id),
    ofx_transacao_id uuid references ofx_transacoes(id),
    tipo text not null,          -- 'boleto' | 'comprovante' | 'outro'
    nome_arquivo text not null,
    storage_path text not null,  -- caminho dentro do bucket "anexos"
    hash_arquivo text unique,    -- detecta reenvio do mesmo arquivo (null em anexos antigos, sem problema)
    created_at timestamptz not null default now()
);

create index on anexos (lancamento_previsto_id);
create index on anexos (ofx_transacao_id);

create index on lancamentos_previstos (empresa_id, status, data_vencimento);
create index on lancamentos_previstos (tipo, status);
create index on lancamentos_previstos (grupo_id);

create index on ofx_transacoes (conta_bancaria_id, data, valor);
create index on movimentacoes_comissao (cliente_id);
create index on lotes_comissao (status);

-- RLS vem habilitada por padrão no Supabase. Este é um app interno (sem
-- login de usuário final ainda) acessado só pela chave publishable/anon,
-- então desativamos por enquanto — revisar quando entrar autenticação real.
alter table empresas disable row level security;
alter table contas_bancarias disable row level security;
alter table clientes disable row level security;
alter table apolice_clientes disable row level security;
alter table seguradoras disable row level security;
alter table fornecedores disable row level security;
alter table plano_contas disable row level security;
alter table ofx_importacoes disable row level security;
alter table ofx_transacoes disable row level security;
alter table lotes_comissao disable row level security;
alter table movimentacoes_comissao disable row level security;
alter table auditoria_alertas disable row level security;
alter table regras_identificacao disable row level security;
alter table lancamentos_previstos disable row level security;
alter table regras_classificacao_comissao disable row level security;
alter table regras_parcelamento disable row level security;
alter table anexos disable row level security;
