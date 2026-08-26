-- Migração: plano de contas, fornecedores e classificação de lançamentos
-- Rodar no SQL Editor do Supabase (as tabelas ja existentes nao sao afetadas).

create table fornecedores (
    id uuid primary key default gen_random_uuid(),
    nome text not null,
    documento text,
    created_at timestamptz not null default now()
);

create table plano_contas (
    id uuid primary key default gen_random_uuid(),
    codigo text not null unique,
    nome text not null,
    tipo text not null,
    conta_pai_id uuid references plano_contas(id),
    created_at timestamptz not null default now()
);

alter table ofx_transacoes add column cliente_id uuid references clientes(id);
alter table ofx_transacoes add column fornecedor_id uuid references fornecedores(id);
alter table ofx_transacoes add column plano_conta_id uuid references plano_contas(id);

create table regras_identificacao (
    id uuid primary key default gen_random_uuid(),
    padrao_descricao text not null,
    cliente_id uuid references clientes(id),
    fornecedor_id uuid references fornecedores(id),
    plano_conta_id uuid references plano_contas(id),
    created_at timestamptz not null default now()
);

alter table fornecedores disable row level security;
alter table plano_contas disable row level security;
alter table regras_identificacao disable row level security;
