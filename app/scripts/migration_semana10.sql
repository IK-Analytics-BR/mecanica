-- ============================================================
-- Migration Semana 10: boletos — IKFlow Mecânica
-- Executar: mysql -u ikflow -p'IkFl0w@2024!DB' supply_chain_mecanica < app/scripts/migration_semana10.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS boletos (
    id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id        INT UNSIGNED  NOT NULL DEFAULT 1,
    service_order_id  INT UNSIGNED  NOT NULL,
    payment_id        VARCHAR(60)   NULL,
    status            VARCHAR(30)   NOT NULL DEFAULT 'pending',
    valor             DECIMAL(12,2) NOT NULL DEFAULT 0,
    vencimento        DATE          NULL,
    boleto_url        VARCHAR(800)  NULL,
    barcode           VARCHAR(200)  NULL,
    resposta_mp       TEXT          NULL,
    criado_em         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_boleto_os      (service_order_id),
    INDEX idx_boleto_payment (payment_id),
    INDEX idx_boleto_company (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── 2. Log de importações ETL ────────────────────────────────
CREATE TABLE IF NOT EXISTS etl_log (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id  INT UNSIGNED NOT NULL DEFAULT 1,
    tipo        VARCHAR(30)  NOT NULL,
    total       INT          NOT NULL DEFAULT 0,
    importados  INT          NOT NULL DEFAULT 0,
    erros       INT          NOT NULL DEFAULT 0,
    detalhes    TEXT         NULL,
    criado_em   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_etl_company (company_id),
    INDEX idx_etl_tipo    (tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SELECT 'Migration Semana 10 (boletos + etl_log) concluída.' AS resultado;
