-- Migração: guarda a conexão de Open Finance (via Pluggy) de cada conta
-- bancária cadastrada — qual "item" (banco conectado) e "account" (conta
-- dentro daquele banco) do Pluggy corresponde a cada conta_bancaria nossa.
-- Sem isso não dá pra saber de qual conta puxar o extrato automaticamente.

create table integracoes_bancarias (
    id uuid primary key default gen_random_uuid(),
    conta_bancaria_id uuid not null references contas_bancarias(id),
    provedor text not null default 'pluggy',
    pluggy_item_id text not null,
    pluggy_account_id text,          -- preenchido depois de escolher a conta dentro do item conectado
    status text not null default 'conectando',  -- 'conectando' | 'ativo' | 'erro' | 'desconectado'
    ultima_sincronizacao timestamptz,
    created_at timestamptz not null default now(),
    unique (conta_bancaria_id)
);

alter table integracoes_bancarias disable row level security;
