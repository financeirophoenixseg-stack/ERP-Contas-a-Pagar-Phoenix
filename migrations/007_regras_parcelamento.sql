-- Migração: regra de parcelamento por apólice (auto/RE) — número total
-- de parcelas esperadas, para provisionar as restantes automaticamente.
-- Rodar no SQL Editor do Supabase.

create table regras_parcelamento (
    id uuid primary key default gen_random_uuid(),
    apolice text not null unique,
    cliente_id uuid references clientes(id),
    total_parcelas int not null,
    created_at timestamptz not null default now()
);

alter table regras_parcelamento disable row level security;
