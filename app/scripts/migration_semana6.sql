-- ============================================================
-- Migration Semana 6: km_historico — IKFlow Mecânica
-- Executar: mysql -u ikflow -p'IkFl0w@2024!DB' supply_chain_mecanica < app/scripts/migration_semana6.sql
-- ============================================================

DROP PROCEDURE IF EXISTS migration_semana6;
DELIMITER //
CREATE PROCEDURE migration_semana6()
BEGIN

  -- ── 1. Histórico de KM por veículo ───────────────────────────────────────
  -- Cada OS registra o KM de entrada; este log permite ver a evolução
  CREATE TABLE IF NOT EXISTS km_historico (
    id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id        INT UNSIGNED NOT NULL DEFAULT 1,
    equipment_id      INT UNSIGNED NOT NULL,
    service_order_id  INT UNSIGNED NULL,
    km                INT UNSIGNED NOT NULL DEFAULT 0,
    registrado_em     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    origem            ENUM('os','manual') NOT NULL DEFAULT 'os',
    observacao        VARCHAR(200) NULL,
    INDEX idx_km_equipment (equipment_id),
    INDEX idx_km_os        (service_order_id),
    INDEX idx_km_company   (company_id),
    INDEX idx_km_data      (registrado_em)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

  -- ── 2. Coluna km_atual em equipment (se não existir) ─────────────────────
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'equipment'
      AND COLUMN_NAME  = 'km_atual'
  ) THEN
    ALTER TABLE equipment ADD COLUMN km_atual INT UNSIGNED NULL DEFAULT NULL
      COMMENT 'KM registrado na última OS';
  END IF;

  SELECT 'Migration Semana 6 (km_historico + equipment.km_atual) concluída.' AS resultado;

END //
DELIMITER ;

CALL migration_semana6();
DROP PROCEDURE IF EXISTS migration_semana6;
