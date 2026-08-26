-- Schema inicial — ERP Phoenix/Vizentim (Conciliação Bancária + Comissões)
-- Rodar no SQL editor do Supabase.

create table empresas (
    id uuid primary key default gen_random_uuid(),
    nome text not null unique,          -- 'Phoenix', 'Vizentim', ...
    cnpj text unique,                    -- CNPJ do corretor, usado para reconhecer a empresa em demonstrativos de comissão
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

create index on ofx_transacoes (conta_bancaria_id, data, valor);
create index on movimentacoes_comissao (cliente_id);
create index on lotes_comissao (status);

-- RLS vem habilitada por padrão no Supabase. Este é um app interno (sem
-- login de usuário final ainda) acessado só pela chave publishable/anon,
-- então desativamos por enquanto — revisar quando entrar autenticação real.
alter table empresas disable row level security;
alter table contas_bancarias disable row level security;
alter table clientes disable row level security;
alter table seguradoras disable row level security;
alter table fornecedores disable row level security;
alter table plano_contas disable row level security;
alter table ofx_importacoes disable row level security;
alter table ofx_transacoes disable row level security;
alter table lotes_comissao disable row level security;
alter table movimentacoes_comissao disable row level security;
alter table auditoria_alertas disable row level security;
alter table regras_identificacao disable row level security;
