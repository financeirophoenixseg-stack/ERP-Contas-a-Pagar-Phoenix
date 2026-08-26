-- Migração: mapeamento apólice -> cliente (para seguradoras cujo demonstrativo
-- não traz nome de cliente/empresa, ex.: Bradesco Saúde).
-- Rodar no SQL Editor do Supabase.

create table apolice_clientes (
    id uuid primary key default gen_random_uuid(),
    apolice text not null unique,
    cliente_id uuid not null references clientes(id),
    created_at timestamptz not null default now()
);

alter table apolice_clientes disable row level security;
