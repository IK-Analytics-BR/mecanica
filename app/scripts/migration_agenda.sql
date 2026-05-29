-- Migration: Agenda de Mecânicos
-- Compatível com MySQL 5.7+
-- Executar: mysql -u ikflow -p'IkFl0w@2024!DB' supply_chain_mecanica < app/scripts/migration_agenda.sql

DROP PROCEDURE IF EXISTS migration_agenda;

DELIMITER //
CREATE PROCEDURE migration_agenda()
BEGIN
  -- agendado_para
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'service_orders' AND COLUMN_NAME = 'agendado_para'
  ) THEN
    ALTER TABLE service_orders ADD COLUMN agendado_para DATE NULL COMMENT 'Data agendada para execução';
  END IF;

  -- hora_inicio
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'service_orders' AND COLUMN_NAME = 'hora_inicio'
  ) THEN
    ALTER TABLE service_orders ADD COLUMN hora_inicio TIME NULL COMMENT 'Hora de início agendada';
  END IF;

  -- hora_fim
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'service_orders' AND COLUMN_NAME = 'hora_fim'
  ) THEN
    ALTER TABLE service_orders ADD COLUMN hora_fim TIME NULL COMMENT 'Hora de fim agendada';
  END IF;

  -- phone_notificado
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'service_orders' AND COLUMN_NAME = 'phone_notificado'
  ) THEN
    ALTER TABLE service_orders ADD COLUMN phone_notificado DATETIME NULL COMMENT 'Última notificação WA enviada';
  END IF;

  -- índice agendado_para
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'service_orders' AND INDEX_NAME = 'idx_agendado_para'
  ) THEN
    ALTER TABLE service_orders ADD INDEX idx_agendado_para (agendado_para);
  END IF;

  -- índice technician + data
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'service_orders' AND INDEX_NAME = 'idx_technician_data'
  ) THEN
    ALTER TABLE service_orders ADD INDEX idx_technician_data (technician_id, agendado_para);
  END IF;

  SELECT 'Migration agenda concluída.' AS resultado;
END //
DELIMITER ;

CALL migration_agenda();
DROP PROCEDURE IF EXISTS migration_agenda;
