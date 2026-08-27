-- Migração: código de comissionado (Hapvida identifica o corretor por um
-- código próprio, ex.: '08LH', nem CNPJ nem SUSEP). Rodar no SQL Editor.

alter table empresas add column codigo_comissionado text unique;
