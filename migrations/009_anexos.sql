-- Migração: tabela de anexos (boletos/comprovantes), ligados ao bucket de
-- Storage "anexos" (criado manualmente no painel). Rodar no SQL Editor.

create table anexos (
    id uuid primary key default gen_random_uuid(),
    lancamento_previsto_id uuid references lancamentos_previstos(id),
    ofx_transacao_id uuid references ofx_transacoes(id),
    tipo text not null,
    nome_arquivo text not null,
    storage_path text not null,
    created_at timestamptz not null default now()
);

create index on anexos (lancamento_previsto_id);
create index on anexos (ofx_transacao_id);

alter table anexos disable row level security;
