-- ============================================================
-- Migration Semana 5: Comissões + Garantias — IKFlow Mecânica
-- Executar: mysql -u ikflow -p'IkFl0w@2024!DB' supply_chain_mecanica < app/scripts/migration_semana5.sql
-- ============================================================

DROP PROCEDURE IF EXISTS migration_semana5;
DELIMITER //
CREATE PROCEDURE migration_semana5()
BEGIN

  -- ── 1. Tabela de Comissões por Mecânico ──────────────────────────────────
  CREATE TABLE IF NOT EXISTS comissoes (
    id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id        INT UNSIGNED NOT NULL DEFAULT 1,
    technician_id     INT UNSIGNED NOT NULL,
    service_order_id  INT UNSIGNED NOT NULL,
    periodo_ref       DATE         NOT NULL COMMENT 'Primeiro dia do mês de referência',
    valor_os          DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    percentual        DECIMAL(5,2)  NOT NULL DEFAULT 10.00 COMMENT '% comissão configurada',
    valor_comissao    DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    status            ENUM('pendente','pago','cancelado') NOT NULL DEFAULT 'pendente',
    pago_em           DATETIME     NULL,
    observacao        VARCHAR(300) NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_comissoes_tecnico  (technician_id),
    INDEX idx_comissoes_os       (service_order_id),
    INDEX idx_comissoes_periodo  (periodo_ref),
    INDEX idx_comissoes_company  (company_id)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

  -- ── 2. Configuração de percentual de comissão por técnico ────────────────
  CREATE TABLE IF NOT EXISTS comissao_config (
    id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id        INT UNSIGNED NOT NULL DEFAULT 1,
    technician_id     INT UNSIGNED NOT NULL,
    percentual        DECIMAL(5,2)  NOT NULL DEFAULT 10.00,
    ativo             TINYINT(1)    NOT NULL DEFAULT 1,
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_comissao_tecnico (company_id, technician_id)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

  -- ── 3. Tabela de Garantias ───────────────────────────────────────────────
  CREATE TABLE IF NOT EXISTS garantias (
    id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id        INT UNSIGNED NOT NULL DEFAULT 1,
    service_order_id  INT UNSIGNED NOT NULL,
    tipo              ENUM('servico','peca','ambos') NOT NULL DEFAULT 'servico',
    descricao         VARCHAR(300) NOT NULL,
    data_inicio       DATE         NOT NULL,
    data_fim          DATE         NOT NULL,
    prazo_dias        INT          NOT NULL DEFAULT 90,
    status            ENUM('vigente','acionada','expirada','cancelada') NOT NULL DEFAULT 'vigente',
    acionada_em       DATETIME     NULL,
    observacao        TEXT         NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_garantias_os      (service_order_id),
    INDEX idx_garantias_company (company_id),
    INDEX idx_garantias_status  (status),
    INDEX idx_garantias_fim     (data_fim)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

  SELECT 'Migration Semana 5 (comissões + garantias) concluída.' AS resultado;

END //
DELIMITER ;

CALL migration_semana5();
DROP PROCEDURE IF EXISTS migration_semana5;
