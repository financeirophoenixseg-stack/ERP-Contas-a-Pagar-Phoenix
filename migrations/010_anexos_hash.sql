-- Migração: hash do arquivo em anexos, pra detectar comprovante/boleto já
-- enviado antes (mesma ideia já usada em ofx_importacoes e lotes_comissao).
-- unique permite múltiplos NULL (anexos antigos, sem hash calculado) sem
-- conflito — só passa a valer pros anexos novos, que sempre calculam o hash.

alter table anexos add column hash_arquivo text unique;
