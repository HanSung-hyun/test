# [인수인계 명세서] 유튜브 전략·기법 지식 베이스(`youtube_strategies`) DB 연동 및 적재 가이드

* **수신 대상**: DB 관리 및 백엔드 / 퀀트 시스템 개발팀 (`E:\키움_rest_api`)
* **발신**: 유튜브 영상 분석 및 기법 추출 파이프라인
* **문서 버전**: v1.0 (시니어 퀀트 아키텍트 교차 검증 및 최종 보완 승인 완료)
* **목적**: 유튜브 영상 분석 파이프라인에서 추출·검증 완료된 1~5편 기법 마스터 JSON 데이터를 프로덕션 DB(`quant_market.db`)에 무결하게 적재하고 향후 퀀트 트레이딩 봇과 연동하기 위한 표준 가이드라인 제공

---

## 1. 아키텍처 개요 및 확정 배경

### 1.1 방안 B (2-테이블 분리 모델) 확정
본 아키텍처는 개별 종목 픽(시계열 트랜잭션 Fact)과 영상 전체를 관통하는 매매 철학·필터·룰(메타데이터 Dimension)의 성격 차이를 명확히 구분하여 설계되었습니다.

1. **기존 트랜잭션 테이블 (`youtube_mentions`)**:
   * 개별 종목명, 종목코드, 언급 초(sec), 진입가/목표가 등 시계열 데이터 저장 (기존 DDL 100% 유지)
2. **신설 지식 차원 테이블 (`youtube_strategies`)**:
   * 비유 6종, 정량/정성 필터, 5대 액셔너블 룰 등 퀀트 봇이 참조할 지식 베이스(Knowledge Base) 전담

> **설계 이점**: 두 테이블 통합 시 발생하는 대량의 NULL(기법 영상의 가격 컬럼 100% NULL)을 0%로 제거하며, 향후 퀀트 봇이 `video_id`를 기반으로 기법과 종목을 $O(1)$ 속도로 교차 분석(JOIN)할 수 있습니다.

### 1.2 시니어 퀀트 검증을 통한 3대 핵심 보완 사항
* **보완 ① [JSON 무결성 제약조건]**: SQLite 특성상 텍스트로 저장되는 JSON 컬럼에 `CHECK(json_valid(...))` 제약조건을 부여하여 잘못된 JSON 적재를 원천 차단.
* **보완 ② [수정 일시 추적]**: 백테스팅 튜닝 후 룰이 변경될 수 있으므로 `updated_at` 컬럼을 추가하여 이력 관리.
* **보완 ③ [JOIN 성능 최적화]**: 기존 `youtube_mentions` 테이블의 `video_id` 컬럼에 인덱스(`idx_mentions_video_id`)를 신설하여 대량 조인 시 Full Table Scan 방지.

---

## 2. 데이터베이스 스키마 및 DDL 명세

* **대상 DB 파일**: `E:\키움_rest_api\database\quant_market.db` (SQLite3)

### 2.1 신설 테이블 DDL: `youtube_strategies`

```sql
-- ==============================================================================
-- 신설 테이블: 유튜브 전략 및 기법 지식 베이스 (youtube_strategies)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS youtube_strategies (
    video_id                  TEXT PRIMARY KEY,                     -- 영상 ID / 폴더명 / 고유 식별자
    video_title               TEXT NOT NULL,                        -- 영상 제목
    category                  TEXT NOT NULL,                        -- 카테고리 ('매매 기법 및 심법', '실전 매매복기' 등)
    main_concept              TEXT,                                 -- 핵심 매매 철학 및 세력 개입 원리
    psychological_warnings    TEXT,                                 -- 계좌 심리 및 경고 (뇌동매매/조급함 방지)
    
    -- JSON 컬럼 (무결성 검증 제약조건 완비)
    key_analogies             JSON CHECK(key_analogies IS NULL OR json_valid(key_analogies) = 1),
    quantitative_filters      JSON CHECK(quantitative_filters IS NULL OR json_valid(quantitative_filters) = 1),
    qualitative_filters       JSON CHECK(qualitative_filters IS NULL OR json_valid(qualitative_filters) = 1),
    actionable_rules          JSON CHECK(actionable_rules IS NULL OR json_valid(actionable_rules) = 1),
    
    created_at                DATETIME DEFAULT CURRENT_TIMESTAMP,   -- 최초 적재 일시
    updated_at                DATETIME DEFAULT CURRENT_TIMESTAMP    -- 최종 수정 일시
);

-- 카테고리 및 생성일자 조회 최적화 인덱스
CREATE INDEX IF NOT EXISTS idx_strategies_category ON youtube_strategies (category);
CREATE INDEX IF NOT EXISTS idx_strategies_created_at ON youtube_strategies (created_at);
```

### 2.2 기존 테이블 보완 DDL: `youtube_mentions` 조인 인덱스

```sql
-- ==============================================================================
-- 기존 youtube_mentions 테이블 조인 성능 최적화 인덱스 추가
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_mentions_video_id ON youtube_mentions (video_id);
```

### 2.3 테이블 관계도 (ERD)

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
|     updated_at                     |             +------------------------------------+    |
+------------------------------------+                                                       |
                                                   +------------------------------------+    |
                                                   |            stock_master            |    |
                                                   +------------------------------------+    |
                                                   | PK  code                           |<---+
                                                   |     name, market, sector ...       |
                                                   +------------------------------------+
```

---

## 3. 입력 데이터 소스 규격 (JSON ↔ DB 매핑)

### 3.1 입력 JSON 파일 위치
* 저장소: Git Repository 내 `결과물/` 디렉터리
* 대상 파일:
  1. `1편_추석_눌림기법_결과.json`
  2. `2편_눌림기법_만들기_결과.json`
  3. `3편_세력돈쓴구간_결과.json`
  4. `4편_지옥같은변동성장_결과.json`
  5. `5편_S급_종목선정_기준_결과.json`

### 3.2 JSON ↔ DB 컬럼 1:1 매핑 명세표

| 마스터 JSON 키 | DB 컬럼명 | SQLite 타입 | 매핑 설명 및 데이터 예시 |
| :--- | :--- | :--- | :--- |
| `(식별자 규칙 참조)` | `video_id` | TEXT (PK) | 영상 식별자 (폴더명 또는 표준 ID) |
| `video_title` | `video_title` | TEXT | 영상 원본 제목 |
| `category` | `category` | TEXT | '매매 기법 및 심법' 등 분류명 |
| `core_philosophy.main_concept` | `main_concept` | TEXT | 핵심 매매 철학 및 세력 개입 원리 |
| `core_philosophy.psychological_warnings` | `psychological_warnings` | TEXT | 심법 경고 및 계좌 관리 원칙 |
| `core_philosophy.key_analogies` | `key_analogies` | JSON (TEXT) | 비유 6종 객체 배열 (JSON 직렬화) |
| `quantitative_filters` | `quantitative_filters` | JSON (TEXT) | 가격, 거래대금, 차트위치 등 정량 필터 객체 |
| `qualitative_filters` | `qualitative_filters` | JSON (TEXT) | 재료 강도, 시장 적응 등 정성 필터 객체 |
| `actionable_rules` | `actionable_rules` | JSON (TEXT) | 5대 액셔너블 룰 배열 (FILTER, EXECUTION 등) |
| *(자동 생성)* | `created_at` | DATETIME | 최초 INSERT 일시 |
| *(자동 생성)* | `updated_at` | DATETIME | 최종 UPDATE 일시 |

### 3.3 1~5편 표준 영상 식별자(`video_id`) 매핑 기준표

다른 프로젝트에서 `youtube_mentions`의 `video_id`와 매칭할 때 다음 매핑 테이블을 참조하십시오:

| 순번 | JSON 파일명 | 권장 video_id (폴더/URL 규격) | 약칭 video_id |
| :---: | :--- | :--- | :--- |
| **1편** | `1편_추석_눌림기법_결과.json` | `[20260925]_[추석 연휴 선물 후속 기법을 만드는 뼈대 - 시작이자 끝. 이대로만 따라 하면 할 수 있는 눌림 기법 만들기]` | `chuseok_breakout_01` |
| **2편** | `2편_눌림기법_만들기_결과.json` | `[20260925]_[추석 연휴 선물 후속 - 이대로만 따라 하면 할 수 있는 눌림 기법 만들기 2편]` | `pullback_setup_02` |
| **3편** | `3편_세력돈쓴구간_결과.json` | `[20261002]_[심플 관심종목 TV]_[직장인이 하기 편한 세력이 돈 쓴 구간을 이용한 눌림매매 !!]` | `smart_money_zone_03` |
| **4편** | `4편_지옥같은변동성장_결과.json` | `kfGbsHAhQe8` *(지옥같은 변동성 장에서도 수익내는 법)* | `extreme_volatility_04` |
| **5편** | `5편_S급_종목선정_기준_결과.json` | `Re-XEQFZvWM` *(S급 종목선정 기준은 ??)* | `s_tier_stock_pick_05` |

---

## 4. 프로덕션 데이터 적재 파이썬 스크립트

다른 프로젝트에서 즉시 복사하여 실행할 수 있는 독립형(Standalone) 적재 파이프라인 코드입니다.
* **특징**: `INSERT ... ON CONFLICT(video_id) DO UPDATE`를 적용하여 몇 번을 재실행해도 안전한 **멱등성(Idempotency)** 보장.

```python
"""
파일: load_strategies_to_quant_db.py
설명: 결과물/*.json 파일들을 파싱하여 quant_market.db의 youtube_strategies 테이블에 적재
사용법: python load_strategies_to_quant_db.py
"""

import os
import json
import sqlite3
from pathlib import Path

# 1. 경로 설정
DB_PATH = r"E:\키움_rest_api\database\quant_market.db"
JSON_DIR = r".\결과물"  # Git 레포지토리 내 결과물 폴더 경로

# 2. 파일별 video_id 매핑 테이블 (프로젝트 환경에 맞춰 선택)
VIDEO_ID_MAPPING = {
    "1편_추석_눌림기법_결과.json": "[20260925]_[추석 연휴 선물 후속 기법을 만드는 뼈대 - 시작이자 끝. 이대로만 따라 하면 할 수 있는 눌림 기법 만들기]",
    "2편_눌림기법_만들기_결과.json": "[20260925]_[추석 연휴 선물 후속 - 이대로만 따라 하면 할 수 있는 눌림 기법 만들기 2편]",
    "3편_세력돈쓴구간_결과.json": "[20261002]_[심플 관심종목 TV]_[직장인이 하기 편한 세력이 돈 쓴 구간을 이용한 눌림매매 !!]",
    "4편_지옥같은변동성장_결과.json": "kfGbsHAhQe8",
    "5편_S급_종목선정_기준_결과.json": "Re-XEQFZvWM"
}

def init_db(conn: sqlite3.Connection):
    """테이블 및 인덱스 초기화"""
    cursor = conn.cursor()
    
    # youtube_strategies 테이블 생성
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS youtube_strategies (
        video_id                  TEXT PRIMARY KEY,
        video_title               TEXT NOT NULL,
        category                  TEXT NOT NULL,
        main_concept              TEXT,
        psychological_warnings    TEXT,
        key_analogies             JSON CHECK(key_analogies IS NULL OR json_valid(key_analogies) = 1),
        quantitative_filters      JSON CHECK(quantitative_filters IS NULL OR json_valid(quantitative_filters) = 1),
        qualitative_filters       JSON CHECK(qualitative_filters IS NULL OR json_valid(qualitative_filters) = 1),
        actionable_rules          JSON CHECK(actionable_rules IS NULL OR json_valid(actionable_rules) = 1),
        created_at                DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at                DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategies_category ON youtube_strategies (category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategies_created_at ON youtube_strategies (created_at);")
    
    # 기존 youtube_mentions 테이블 조인 인덱스 생성
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_video_id ON youtube_mentions (video_id);")
    conn.commit()
    print("[SUCCESS] 테이블 스키마 및 인덱스 초기화 완료.")

def ingest_json_files(conn: sqlite3.Connection, json_dir_path: str):
    """결과물 디렉터리의 JSON 파일들을 읽어 DB에 적재"""
    cursor = conn.cursor()
    target_dir = Path(json_dir_path)
    
    if not target_dir.exists():
        raise FileNotFoundError(f"JSON 디렉터리를 찾을 수 없습니다: {json_dir_path}")

    json_files = sorted(target_dir.glob("*.json"))
    print(f"[*] 적재 대상 JSON 파일 수: {len(json_files)}개")

    upsert_sql = """
    INSERT INTO youtube_strategies (
        video_id,
        video_title,
        category,
        main_concept,
        psychological_warnings,
        key_analogies,
        quantitative_filters,
        qualitative_filters,
        actionable_rules,
        updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(video_id) DO UPDATE SET
        video_title = excluded.video_title,
        category = excluded.category,
        main_concept = excluded.main_concept,
        psychological_warnings = excluded.psychological_warnings,
        key_analogies = excluded.key_analogies,
        quantitative_filters = excluded.quantitative_filters,
        qualitative_filters = excluded.qualitative_filters,
        actionable_rules = excluded.actionable_rules,
        updated_at = CURRENT_TIMESTAMP;
    """

    for file_path in json_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # video_id 결정 (매핑 테이블 참조 또는 파일명 스템 사용)
        filename = file_path.name
        video_id = VIDEO_ID_MAPPING.get(filename, file_path.stem)

        video_title = data.get("video_title", "")
        category = data.get("category", "매매 기법 및 심법")
        
        core_phil = data.get("core_philosophy", {})
        main_concept = core_phil.get("main_concept", "")
        psych_warnings = core_phil.get("psychological_warnings", "")
        
        # JSON 직렬화 (인코딩 보장)
        key_analogies_json = json.dumps(core_phil.get("key_analogies", []), ensure_ascii=False)
        quant_filters_json = json.dumps(data.get("quantitative_filters", {}), ensure_ascii=False)
        qual_filters_json = json.dumps(data.get("qualitative_filters", {}), ensure_ascii=False)
        action_rules_json = json.dumps(data.get("actionable_rules", []), ensure_ascii=False)

        cursor.execute(upsert_sql, (
            video_id,
            video_title,
            category,
            main_concept,
            psych_warnings,
            key_analogies_json,
            quant_filters_json,
            qual_filters_json,
            action_rules_json
        ))
        print(f" -> 적재 완료: [{filename}] => video_id: '{video_id}'")

    conn.commit()
    print("[SUCCESS] 모든 기법 마스터 데이터 적재 성공.")

if __name__ == "__main__":
    if not os.path.exists(os.path.dirname(DB_PATH)):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    db_conn = sqlite3.connect(DB_PATH)
    try:
        init_db(db_conn)
        ingest_json_files(db_conn, JSON_DIR)
    finally:
        db_conn.close()
```

---

## 5. 데이터 적재 후 무결성 검증 쿼리 세트

적재가 정상적으로 완료되었는지 확인하기 위해 다음 4대 검증 쿼리를 수행하십시오.

### 5.1 적재 레코드 총 건수 및 카테고리 확인
```sql
SELECT video_id, category, video_title, created_at, updated_at 
FROM youtube_strategies;
-- 기대 결과: 5건 반환, category='매매 기법 및 심법'
```

### 5.2 JSON 파싱 및 무결성 제약조건 동작 확인
```sql
SELECT 
    video_id,
    json_extract(quantitative_filters, '$.volume_and_effort') AS volume_criteria,
    json_array_length(actionable_rules) AS total_rules_count
FROM youtube_strategies;
-- 기대 결과: 거래대금 기준 텍스트 정상 출력 및 각 영상별 룰 개수(5개 안팎) 표시
```

### 5.3 퀀트 트레이딩 봇 연동 쿼리 (실전 EXECUTION 룰 전수 추출)
```sql
SELECT 
    s.video_id,
    s.video_title,
    json_extract(r.value, '$.condition') AS entry_trigger,
    json_extract(r.value, '$.action_or_mindset') AS execution_action
FROM youtube_strategies s, json_each(s.actionable_rules) r
WHERE json_extract(r.value, '$.rule_type') = 'EXECUTION';
-- 기대 결과: 봇의 룰 엔진에 즉시 주입 가능한 실전 진입/타점 룰 리스트 추출
```

### 5.4 `youtube_mentions`와의 크로스 JOIN 쿼리 (전략 ↔ 추천 종목 매핑)
```sql
SELECT 
    s.video_title,
    s.main_concept,
    m.stock_name,
    m.stock_code,
    m.entry_price_1st,
    m.direction
FROM youtube_strategies s
JOIN youtube_mentions m ON s.video_id = m.video_id
ORDER BY m.video_date DESC;
-- 기대 결과: 인덱스(idx_mentions_video_id)를 통해 고속 매칭 확인
```

---

## 6. 향후 운영 및 파이프라인 가이드

1. **신규 영상 추가 시**:
   * 영상 분석 파이프라인에서 추출된 신규 `[N편_*_결과.json]` 파일을 `결과물/` 디렉터리에 추가하고 적재 스크립트를 재실행하면 신규 레코드만 자동으로 추가됩니다.
2. **전략 파라미터 튜닝 시**:
   * 백테스팅 후 특정 기법의 수치(예: 이동평균선, RSI 타점)가 개선되어 JSON이 수정된 경우, 스크립트를 재실행하면 `ON CONFLICT DO UPDATE` 구문에 의해 기존 데이터가 갱신되고 `updated_at` 타임스탬프가 최신 일시로 자동 갱신됩니다.
3. **데이터베이스 백업**:
   * 테이블 변경 작업 전 `quant_market.db`의 백업 복사본 생성을 권장합니다.
