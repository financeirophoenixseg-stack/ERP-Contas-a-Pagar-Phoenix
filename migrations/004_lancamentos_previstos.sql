-- Migração: contas a pagar/receber previstas (avulsas, parceladas, fixas).
-- Rodar no SQL Editor do Supabase.

create table lancamentos_previstos (
    id uuid primary key default gen_random_uuid(),
    empresa_id uuid not null references empresas(id),
    tipo text not null,
    descricao text not null,
    valor numeric(14,2) not null,
    data_vencimento date not null,
    status text not null default 'previsto',
    data_pagamento date,
    cliente_id uuid references clientes(id),
    fornecedor_id uuid references fornecedores(id),
    plano_conta_id uuid references plano_contas(id),
    conta_bancaria_id uuid references contas_bancarias(id),
    ofx_transacao_id uuid references ofx_transacoes(id),
    grupo_id uuid,
    parcela_atual int,
    parcela_total int,
    recorrente boolean not null default false,
    created_at timestamptz not null default now()
);

create index on lancamentos_previstos (empresa_id, status, data_vencimento);
create index on lancamentos_previstos (tipo, status);
create index on lancamentos_previstos (grupo_id);

alter table lancamentos_previstos disable row level security;
