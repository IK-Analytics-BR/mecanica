-- ============================================================
-- Migration Semana 9: push_subscriptions + portal_tokens — IKFlow Mecânica
-- Executar: mysql -u ikflow -p'IkFl0w@2024!DB' supply_chain_mecanica < app/scripts/migration_semana9.sql
-- ============================================================

-- ── 1. Subscriptions de Web Push ─────────────────────────────
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id  INT UNSIGNED NOT NULL DEFAULT 1,
    user_id     INT UNSIGNED NOT NULL DEFAULT 0,
    endpoint    VARCHAR(800) NOT NULL,
    p256dh      VARCHAR(300) NOT NULL DEFAULT '',
    auth_key    VARCHAR(100) NOT NULL DEFAULT '',
    ativo       TINYINT(1)   NOT NULL DEFAULT 1,
    criado_em   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_endpoint (endpoint(255)),
    INDEX idx_push_company (company_id),
    INDEX idx_push_user    (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── 2. Tokens de acesso do portal do cliente ─────────────────
CREATE TABLE IF NOT EXISTS portal_tokens (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id  INT UNSIGNED NOT NULL DEFAULT 1,
    customer_id INT UNSIGNED NOT NULL,
    token       VARCHAR(64)  NOT NULL,
    expira_em   DATETIME     NOT NULL,
    usado_em    DATETIME     NULL,
    ativo       TINYINT(1)   NOT NULL DEFAULT 1,
    criado_em   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_token (token),
    INDEX idx_portal_customer (customer_id),
    INDEX idx_portal_company  (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SELECT 'Migration Semana 9 (push_subscriptions + portal_tokens) concluída.' AS resultado;
