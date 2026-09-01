-- Transferências entre contas bancárias do próprio grupo (ex.: Sicoob →
-- Bradesco). Lançamento especial: NÃO entra no DRE (não é receita nem
-- despesa, é só dinheiro mudando de lugar) — por isso fica numa tabela
-- própria, separada de lancamentos_previstos.
create table transferencias_contas (
    id uuid primary key default gen_random_uuid(),
    conta_origem_id uuid not null references contas_bancarias(id),
    conta_destino_id uuid not null references contas_bancarias(id),
    valor numeric(14,2) not null,
    data_transferencia date not null,
    descricao text,
    status text not null default 'prevista', -- 'prevista' | 'efetivada' | 'cancelada'
    ofx_transacao_origem_id uuid references ofx_transacoes(id),
    ofx_transacao_destino_id uuid references ofx_transacoes(id),
    created_at timestamptz not null default now()
);

alter table transferencias_contas disable row level security;
