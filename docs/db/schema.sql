-- ============================================================================
-- AntiVishing 실서비스 확장 설계안 — MySQL 8.0 / InnoDB, 3NF 정규화 스키마
--
-- 지금 돌아가는 프로토타입은 backend/app/store.py의 인메모리 dict + CSV 파일로
-- 동작한다. 이 스키마는 "실서비스로 확장한다면"이라는 가정 하에 같은 데이터 모델을
-- 제1정규형(1NF)~제3정규형(3NF)까지 정규화한 설계안이며, 지금 단계에서 실제로
-- 서버에 이 DB를 띄우는 것을 전제로 하지 않는다(프로토타입은 그대로 인메모리로 유지).
--
-- 정규화 포인트 요약
--   1NF: 반복/다중값 속성(사유 목록 reasons, 대화 로그 conversation, 사기패턴
--        signals 키워드 목록)을 한 컬럼에 배열/구분자 문자열로 넣지 않고 각각
--        별도 자식 테이블로 분리했다.
--   2NF: 복합키를 쓰는 테이블(예: case_reasons, case_conversation)에서 키의
--        일부에만 종속되는 속성이 없도록 대리키(surrogate id)를 사용했다.
--   3NF: 기본키가 아닌 속성이 다른 비기본키 속성에 이행적으로 종속되지 않도록
--        했다. 예: recipient_accounts.bank는 계좌 자체 속성이라 cases에 중복
--        저장하지 않고 FK로만 참조한다.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS antivishing DEFAULT CHARACTER SET utf8mb4;
USE antivishing;

-- ----------------------------------------------------------------------------
-- 고객 (창구에 온 사람). 이름+본인 계좌번호로 조회한다("신분증 스캔" 시뮬레이션).
-- ----------------------------------------------------------------------------
CREATE TABLE customers (
    customer_id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                  VARCHAR(50)     NOT NULL,
    account_number        VARCHAR(30)     NOT NULL,
    age                   TINYINT UNSIGNED NOT NULL,
    gender                ENUM('남', '여') NOT NULL,
    balance               BIGINT UNSIGNED NOT NULL DEFAULT 0,
    recent_channel        VARCHAR(100),
    notable_activity      TEXT,                       -- 최근 특이 동향(예: 비대면 대출 이력)
    avg_monthly_tx_count  DECIMAL(6,2)    NOT NULL DEFAULT 0,
    avg_amount            BIGINT UNSIGNED NOT NULL DEFAULT 0,
    max_amount_ever       BIGINT UNSIGNED NOT NULL DEFAULT 0,
    created_at            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_customer_identity (name, account_number)   -- 신분증 스캔 조회 키
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 수취계좌. 계좌번호로 조회한다. early_warning_db_hit/biz_reg_verified는
-- 거래내역만으로 알 수 없는 외부 DB 조회 결과라 별도 컬럼으로 둔다(3NF: 계좌
-- 자체의 속성이며 다른 테이블에 이행적으로 종속되지 않음).
-- ----------------------------------------------------------------------------
CREATE TABLE recipient_accounts (
    recipient_id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    label                 VARCHAR(100)    NOT NULL,   -- 내부 참고용 라벨(화면 비노출)
    bank                  VARCHAR(30)     NOT NULL,
    account_number        VARCHAR(30)     NOT NULL,
    early_warning_db_hit  BOOLEAN         NOT NULL DEFAULT FALSE,
    biz_reg_verified      BOOLEAN         NULL,       -- NULL=조회 대상 아님, TRUE/FALSE=조회 결과
    created_at            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_recipient_account_number (account_number)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 고객별 신뢰 수취인 등록 (M:N). 지금 프로토타입은 고객 1명당 신뢰 수취인이
-- 최대 1개뿐이지만, 실서비스에서는 여러 개일 수 있으므로 조인 테이블로 둔다.
-- ----------------------------------------------------------------------------
CREATE TABLE customer_trusted_recipients (
    customer_id           BIGINT UNSIGNED NOT NULL,
    recipient_id          BIGINT UNSIGNED NOT NULL,
    registered_at         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id, recipient_id),
    FOREIGN KEY (customer_id)  REFERENCES customers(customer_id),
    FOREIGN KEY (recipient_id) REFERENCES recipient_accounts(recipient_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 수취계좌 실제 입출금 내역. 지금은 CSV 파일(backend/app/data/account_transactions/*.csv)로
-- 관리하지만, 실서비스에서는 코어뱅킹/전자금융공동망에서 적재되는 테이블에 해당한다.
-- account_analysis.py의 즉시인출비율/분산입금/심야비중/일평균빈도 계산은 이 테이블에
-- 대한 집계 쿼리로 그대로 옮길 수 있다.
-- ----------------------------------------------------------------------------
CREATE TABLE account_transactions (
    transaction_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    recipient_id           BIGINT UNSIGNED NOT NULL,
    txn_datetime           DATETIME        NOT NULL,
    txn_type               ENUM('입금', '출금') NOT NULL,
    amount                 BIGINT UNSIGNED NOT NULL,
    balance_after          BIGINT UNSIGNED NOT NULL,
    counterparty           VARCHAR(50),
    FOREIGN KEY (recipient_id) REFERENCES recipient_accounts(recipient_id),
    KEY idx_recipient_datetime (recipient_id, txn_datetime)   -- 72h 윈도우 집계용
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 알려진 사기 스크립트 패턴 (자유텍스트 RAG 대조용 참고 문서)
-- ----------------------------------------------------------------------------
CREATE TABLE known_scam_patterns (
    pattern_id             VARCHAR(40)     PRIMARY KEY,   -- 예: PROSECUTOR_IMPERSONATION
    summary                VARCHAR(255)    NOT NULL
) ENGINE=InnoDB;

-- signals는 원래 리스트(다중값)라 1NF 위반을 피하려고 별도 테이블로 분리
CREATE TABLE known_scam_pattern_signals (
    pattern_id             VARCHAR(40)     NOT NULL,
    signal_keyword         VARCHAR(50)     NOT NULL,
    PRIMARY KEY (pattern_id, signal_keyword),
    FOREIGN KEY (pattern_id) REFERENCES known_scam_patterns(pattern_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 케이스 (거래 접수 1건). FSM 상태값은 models.py의 CaseStatus Enum과 동일하게 맞춘다.
-- ----------------------------------------------------------------------------
CREATE TABLE cases (
    case_id                CHAR(8)         PRIMARY KEY,   -- 프로토타입과 동일하게 짧은 uuid 앞 8자리
    teller_id              VARCHAR(30)     NOT NULL,
    customer_id            BIGINT UNSIGNED NOT NULL,
    recipient_id           BIGINT UNSIGNED NOT NULL,
    amount                 BIGINT UNSIGNED NOT NULL,
    already_sent           BOOLEAN         NOT NULL DEFAULT FALSE,
    status                 ENUM(
        'TIER1_LOW_RISK_COMPLETED', 'TIER2_ESCALATED', 'AWAITING_YESNO',
        'AWAITING_FREETEXT', 'STT_HARD_BLOCKED', 'FINAL_HIGH_RISK',
        'FINAL_LOW_RISK', 'GOLDEN_TIME_FREEZE_REQUESTED'
    ) NOT NULL,
    next_action            VARCHAR(30),
    pending_freetext_question TEXT,
    freetext_round          TINYINT UNSIGNED NOT NULL DEFAULT 0,
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id)  REFERENCES customers(customer_id),
    FOREIGN KEY (recipient_id) REFERENCES recipient_accounts(recipient_id),
    KEY idx_status (status)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- Tier1 결과 (케이스당 1개, 1:1). 첫 거래/신뢰수취인/고령자 여부 등 판단 시점의
-- 스냅샷이라 customers 테이블 값이 나중에 바뀌어도 그 시점 판단 근거가 보존된다.
-- ----------------------------------------------------------------------------
CREATE TABLE tier1_results (
    case_id                CHAR(8)         PRIMARY KEY,
    is_trusted_recipient   BOOLEAN         NOT NULL,
    is_first_time          BOOLEAN         NOT NULL,
    is_elderly_customer    BOOLEAN         NOT NULL,
    amount_ratio_vs_max    DECIMAL(10,2)   NOT NULL,
    escalate_to_tier2      BOOLEAN         NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- Tier2 결과 (케이스당 1개, 1:1, Tier2로 확대된 케이스만 존재).
-- account_features의 4개 지표는 다중값이 아니라 각각 독립된 스칼라 사실이므로
-- 컬럼으로 두어도 정규형 위반이 아니다(반복 그룹이 아님).
-- ----------------------------------------------------------------------------
CREATE TABLE tier2_analyses (
    case_id                     CHAR(8)         PRIMARY KEY,
    auto_suspicion_score         TINYINT UNSIGNED NOT NULL,
    high_auto_signal             BOOLEAN         NOT NULL,
    anomaly_flag                 BOOLEAN         NOT NULL,
    immediate_withdrawal_ratio   DECIMAL(4,3),
    distinct_senders_72h         SMALLINT UNSIGNED,
    night_txn_ratio               DECIMAL(4,3),
    txn_frequency_per_day         DECIMAL(6,2),
    FOREIGN KEY (case_id) REFERENCES cases(case_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 케이스별 판단 사유 목록 (tier1/tier2 reasons 배열의 1NF 정규화).
-- 원래 API 응답에서는 문자열 리스트였던 것을 (case_id, source, seq) 로 펼친다.
-- ----------------------------------------------------------------------------
CREATE TABLE case_reasons (
    reason_id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    case_id                CHAR(8)         NOT NULL,
    source                 ENUM('tier1', 'tier2') NOT NULL,
    seq                    TINYINT UNSIGNED NOT NULL,   -- 원래 배열에서의 순서
    reason_text            VARCHAR(255)    NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id),
    KEY idx_case_source (case_id, source)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- STT 코칭 정황 분석 결과 (케이스당 1개, 1:1)
-- ----------------------------------------------------------------------------
CREATE TABLE stt_results (
    case_id                CHAR(8)         PRIMARY KEY,
    coaching_detected      BOOLEAN         NOT NULL,
    confidence             DECIMAL(3,2)    NOT NULL,
    matched_scam_type      VARCHAR(50),
    reasoning              TEXT,
    transcript             TEXT            NOT NULL,
    analyzed_at            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES cases(case_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- Y/N 확인 결과 (케이스당 1개, 1:1)
-- ----------------------------------------------------------------------------
CREATE TABLE yesno_answers (
    case_id                CHAR(8)         PRIMARY KEY,
    known_recipient        BOOLEAN         NOT NULL,
    aware_of_true_purpose  BOOLEAN         NOT NULL,
    clearly_normal         BOOLEAN         NOT NULL,
    answered_at            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES cases(case_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 자유텍스트 LLM 대조 결과 (케이스당 최대 3라운드, 1:N)
-- ----------------------------------------------------------------------------
CREATE TABLE freetext_analyses (
    freetext_id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    case_id                CHAR(8)         NOT NULL,
    round_no               TINYINT UNSIGNED NOT NULL,
    customer_statement     TEXT            NOT NULL,
    risk_level             ENUM('low', 'medium', 'high') NOT NULL,
    matched_pattern_id     VARCHAR(40),
    needs_followup         BOOLEAN         NOT NULL,
    followup_question      TEXT,
    reasoning              TEXT,
    analyzed_at            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES cases(case_id),
    FOREIGN KEY (matched_pattern_id) REFERENCES known_scam_patterns(pattern_id),
    UNIQUE KEY uq_case_round (case_id, round_no)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 직원-고객 간 실제 대화 로그 (STT/Y-N/자유텍스트 모두 포함, 1:N).
-- conversation 배열의 1NF 정규화.
-- ----------------------------------------------------------------------------
CREATE TABLE case_conversation (
    conversation_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    case_id                CHAR(8)         NOT NULL,
    seq                    SMALLINT UNSIGNED NOT NULL,
    question               VARCHAR(255)    NOT NULL,
    answer                 TEXT            NOT NULL,
    created_at             DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES cases(case_id),
    UNIQUE KEY uq_case_seq (case_id, seq)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 최종 판정 (케이스당 1개, 1:1)
-- ----------------------------------------------------------------------------
CREATE TABLE final_decisions (
    case_id                CHAR(8)         PRIMARY KEY,
    risk_level             ENUM('low', 'high') NOT NULL,
    trigger_reason         VARCHAR(50)     NOT NULL,   -- stt_hard_block | freetext_high_risk | ...
    explanation            TEXT            NOT NULL,   -- LLM이 생성한 XAI 자연어 설명
    decided_at             DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES cases(case_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 에스컬레이션 조치 기록 (케이스당 여러 건 가능, 1:N)
-- ----------------------------------------------------------------------------
CREATE TABLE escalation_actions (
    escalation_id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    case_id                CHAR(8)         NOT NULL,
    action                 ENUM('confirm_with_sender', 'escalate_fsi', 'notify_guardian', 'freeze_request') NOT NULL,
    created_at             DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES cases(case_id)
) ENGINE=InnoDB;
