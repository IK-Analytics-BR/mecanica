-- ============================================================
-- Migration Semana 7: audit_log — IKFlow Mecânica
-- Executar: mysql -u ikflow -p'IkFl0w@2024!DB' supply_chain_mecanica < app/scripts/migration_semana7.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id    INT UNSIGNED    NOT NULL DEFAULT 1,
    tabela        VARCHAR(80)     NOT NULL,
    registro_id   INT UNSIGNED    NOT NULL DEFAULT 0,
    acao          ENUM('create','update','delete','login','logout','approve','cancel') NOT NULL,
    usuario       VARCHAR(120)    NOT NULL DEFAULT 'sistema',
    ip            VARCHAR(45)     NULL,
    dados_antes   JSON            NULL,
    dados_depois  JSON            NULL,
    criado_em     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_company  (company_id),
    INDEX idx_audit_tabela   (tabela, registro_id),
    INDEX idx_audit_usuario  (usuario),
    INDEX idx_audit_data     (criado_em)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SELECT 'Migration Semana 7 (audit_log) concluída.' AS resultado;
