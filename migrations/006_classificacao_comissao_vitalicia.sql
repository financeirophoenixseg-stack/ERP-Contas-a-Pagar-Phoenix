-- Migração: classificação agenciamento x vitalício por cliente, e provisão
-- de receita futura quando detectar comissão vitalícia.
-- Rodar no SQL Editor do Supabase.

alter table movimentacoes_comissao add column categoria text;
alter table lancamentos_previstos add column apolice text;

create table regras_classificacao_comissao (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null unique references clientes(id),
    parcelas_agenciamento int not null default 0,
    percentual_agenciamento numeric(5,2),
    percentual_vitalicio numeric(5,2),
    meses_provisionar int not null default 24,
    created_at timestamptz not null default now()
);

alter table regras_classificacao_comissao disable row level security;
