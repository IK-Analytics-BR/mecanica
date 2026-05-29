-- Migration: Agenda de Mecânicos
-- Adiciona colunas de agendamento na tabela service_orders
-- Executar: mysql -u ikflow -p'IkFl0w@2024!DB' supply_chain_mecanica < migration_agenda.sql

ALTER TABLE service_orders
  ADD COLUMN IF NOT EXISTS agendado_para DATE        NULL COMMENT 'Data agendada para execução',
  ADD COLUMN IF NOT EXISTS hora_inicio   TIME        NULL COMMENT 'Hora de início agendada',
  ADD COLUMN IF NOT EXISTS hora_fim      TIME        NULL COMMENT 'Hora de fim agendada',
  ADD COLUMN IF NOT EXISTS phone_notificado DATETIME NULL COMMENT 'Última notificação WA enviada';

-- Índice para facilitar queries do calendário
ALTER TABLE service_orders
  ADD INDEX IF NOT EXISTS idx_agendado_para (agendado_para),
  ADD INDEX IF NOT EXISTS idx_technician_data (technician_id, agendado_para);

SELECT 'Migration agenda concluída.' AS resultado;
