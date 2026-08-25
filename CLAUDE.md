# ERP Phoenix/Vizentim — Conciliação Bancária + Comissões

Leia [PLANO.md](PLANO.md) primeiro — tem o escopo de negócio completo, modelo de dados, cronograma de 6 semanas e decisões de arquitetura.

Resumo rápido:
- Stack: Streamlit + Supabase (Postgres) + Python.
- Domínio: concilia extratos bancários (OFX) das empresas Phoenix e Vizentim com demonstrativos de comissão de seguradoras (começando por Suhai).
- Projeto **independente** de qualquer outro ERP Phoenix nesta máquina (ex.: `Phoenix-Web-Multiusuario-MVP-v5.12` é um sistema diferente, de conferência de faturamento de plano de saúde — não misturar).
- Prazo: 17/08/2026 → 28/09/2026.
