# [최종 검증 요청] 방안 B 기반 퀀트 지식 베이스 DB 아키텍처 상세 설계안

## 1. 아키텍처 확정 개요
시니어 퀀트 아키텍트의 자문 피드백을 100% 수용하여, 단일 DB 파일(`E:\키움_rest_api\database\quant_market.db`) 내에서 **[트랜잭션(Fact) 테이블]**과 **[지식/전략(Dimension) 테이블]**을 명확히 분리하는 **[방안 B]**로 최종 설계를 확정하였습니다.

* **기존 테이블 (`youtube_mentions`)**: 종목명, 종목코드, 타임스탬프, 매수/목표가 등 **개별 종목 멘션 및 매매복기 트랜잭션** 유지
* **신설 테이블 (`youtube_strategies`)**: 매매 철학, 비유 6종, 정량/정성 필터, 5대 액셔너블 룰 등 **전략 메타데이터(Knowledge Base)** 수용

---

## 2. 테이블 간 관계 모델 (ERD)

```text
+------------------------------------+             +------------------------------------+
|        youtube_strategies          |             |          youtube_mentions          |
|      (Dimension / Knowledge)       |             |          (Fact / Signal)           |
+------------------------------------+             +------------------------------------+
| PK  video_id                       |<---+        | PK  mention_id                     |
|     video_title                    |    |        | FK  video_id                       |-----+ (JOIN)
|     category                       |    +--------|     video_date                     |
|     main_concept                   |  (1 : N)    |     content_type                   |
|     psychological_warnings         |             |     stock_name                     |
|     key_analogies (JSON)           |             | FK  stock_code                     |----+
|     quantitative_filters (JSON)    |             |     time_start_sec                 |    |
|     qualitative_filters (JSON)     |             |     direction                      |    |
|     actionable_rules (JSON)        |             |     entry_price_1st / target_price |    |
|     created_at                     |             |     created_at                     |    |
+------------------------------------+             +------------------------------------+    |
                                                                                             |
                                                   +------------------------------------+    |
                                                   |            stock_master            |    |
                                                   +------------------------------------+    |
                                                   | PK  code                           |<---+
                                                   |     name, market, sector ...       |
                                                   +------------------------------------+
```

---

## 3. 신설 테이블 `youtube_strategies` DDL 명세

SQLite의 네이티브 JSON 지원(`JSON1`)을 활용하여 가독성과 쿼리 성능을 동시에 확보하는 DDL입니다:

```sql
-- ==============================================================================
-- 신설 테이블: 유튜브 전략 및 매매기법 지식 베이스
-- 위치: E:\키움_rest_api\database\quant_market.db
-- ==============================================================================
CREATE TABLE IF NOT EXISTS youtube_strategies (
    video_id                  TEXT PRIMARY KEY,                     -- 영상 ID / 폴더명
    video_title               TEXT NOT NULL,                        -- 영상 제목
    category                  TEXT NOT NULL,                        -- '매매 기법 및 심법', '실전 매매복기' 등
    main_concept              TEXT,                                 -- 핵심 매매 철학 및 세력 개입 원리
    psychological_warnings    TEXT,                                 -- 계좌 심리 및 경고 (편향, 조급함 방지)
    key_analogies             JSON,                                 -- 비유 6종 객체 배열 [{"original_metaphor": ..., "intended_meaning": ...}]
    quantitative_filters      JSON,                                 -- 정량 필터 객체 {"price_and_market_cap": ..., "volume_and_effort": ..., ...}
    qualitative_filters       JSON,                                 -- 정성 필터 객체 {"catalyst_analysis": ..., "market_regime_adaptation": ...}
    actionable_rules          JSON,                                 -- 5대 액셔너블 룰 배열 [{"rule_id": ..., "rule_type": ..., "condition": ..., "action_or_mindset": ...}]
    created_at                DATETIME DEFAULT CURRENT_TIMESTAMP    -- DB 적재 일시
);

-- 카테고리별 초고속 인덱스
CREATE INDEX IF NOT EXISTS idx_strategies_category ON youtube_strategies (category);
CREATE INDEX IF NOT EXISTS idx_strategies_created_at ON youtube_strategies (created_at);
```

---

## 4. 1~5편 마스터 JSON과 DDL 컬럼 1:1 매핑 명세

우리가 추출한 10점 만점 JSON 데이터는 별도의 가공/손실 없이 그대로 컬럼에 매핑됩니다:

| 마스터 JSON 키 | DB 컬럼명 | 데이터 타입 | 비고 |
| :--- | :--- | :--- | :--- |
| `video_title` | `video_title` | TEXT | 영상 제목 |
| `category` | `category` | TEXT | 카테고리 (인덱스 생성) |
| `core_philosophy.main_concept` | `main_concept` | TEXT | 핵심 매매 개념 |
| `core_philosophy.psychological_warnings` | `psychological_warnings` | TEXT | 심법 및 계좌 경고 |
| `core_philosophy.key_analogies` | `key_analogies` | JSON | 비유 배열 (원형 단어 보존) |
| `quantitative_filters` | `quantitative_filters` | JSON | 대금 다다익선, 이평선, RSI 수치 등 |
| `qualitative_filters` | `qualitative_filters` | JSON | 재료 지속성, 시장 투심 양방향 조율 |
| `actionable_rules` | `actionable_rules` | JSON | 5대 액셔너블 룰 배열 |
| (시스템 자동) | `created_at` | DATETIME | 적재 타임스탬프 |

---

## 5. 실전 퀀트 백테스팅 연동 쿼리 시나리오

방안 B를 적용했을 때, 퀀트 트레이딩 봇이 실제로 데이터를 활용하는 3대 쿼리 예시입니다:

### [시나리오 1] 기법 이론과 실제 매매 종목의 교차 분석 (JOIN)
*"S급 종목선정 기법 영상에서 유튜버가 실제로 언급했던 종목들과 매수가를 조회하라"*
```sql
SELECT 
    s.video_title,
    s.main_concept,
    m.stock_name,
    m.stock_code,
    m.entry_price_1st,
    m.time_start_sec
FROM youtube_strategies s
JOIN youtube_mentions m ON s.video_id = m.video_id
WHERE s.category = '매매 기법 및 심법'
ORDER BY m.video_date DESC;
```

### [시나리오 2] 전 영상에서 실행 타점(`EXECUTION`) 룰만 전수 추출
*"모든 전략 영상에서 구체적인 진입/청산 타점만 봇에 로드하라"*
```sql
SELECT 
    video_id,
    video_title,
    json_extract(value, '$.condition') AS entry_condition,
    json_extract(value, '$.action_or_mindset') AS execution_action
FROM youtube_strategies, json_each(youtube_strategies.actionable_rules)
WHERE json_extract(value, '$.rule_type') = 'EXECUTION';
```

### [시나리오 3] 특정 종목(예: 로보티즈)이 속한 영상의 전략 철학 확인
```sql
SELECT 
    m.stock_name,
    m.direction,
    s.main_concept,
    s.psychological_warnings
FROM youtube_mentions m
JOIN youtube_strategies s ON m.video_id = s.video_id
WHERE m.stock_name = '로보티즈';
```

---

## 6. 최종 검증 및 자문 질문
1. 위 `youtube_strategies` DDL 구조 및 매핑 설계가 퀀트 시스템 구축 및 백테스팅 파이프라인 관점에서 완성도가 충분한가요?
2. 추가로 인덱스나 컬럼, 혹은 SQLite 제약조건(Constraint) 측면에서 보완할 미세한 디테일이 있다면 무엇인가요?
3. 이 설계대로 프로덕션 DB(`quant_market.db`)에 즉시 반영하고 1~5편 적재를 진행해도 안전한지 최종 승인 의견을 부탁드립니다.
