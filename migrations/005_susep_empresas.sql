-- Migração: código SUSEP da empresa (Porto Seguro identifica o corretor
-- por SUSEP, não CNPJ). Rodar no SQL Editor do Supabase.

alter table empresas add column susep text unique;
