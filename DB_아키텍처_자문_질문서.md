# [질문] 유튜브 주식 영상 지식 DB 설계: 단일 테이블(통합) vs 2개 테이블(분리) 아키텍처 자문

## 1. 현재 상황 및 기존 DB 구조
현재 유튜브 주식 채널("심플 관심종목 TV")의 270여 개 영상을 분석하여 SQLite DB(`quant_market.db`)에 적재하는 퀀트 지식 베이스를 구축하고 있습니다.

현재 사용 중인 기존 테이블 DDL은 아래와 같습니다:

```sql
CREATE TABLE IF NOT EXISTS youtube_mentions (
    mention_id      TEXT PRIMARY KEY,                     -- 고유 식별자 (예: [20260427]_영상명_m0001)
    video_id        TEXT NOT NULL,                        -- 영상 ID / 폴더명
    video_date      TEXT,                                 -- 영상 일자 (YYYY-MM-DD)
    content_type    TEXT NOT NULL,                        -- STOCK_PICK, STUDY, MINDSET, TRADE_RECAP 등
    time_horizon    TEXT,                                 -- SWING, DAY_TRADING, LONG_TERM 등
    direction       TEXT,                                 -- BUY, SELL, WATCH
    time_start_sec  REAL NOT NULL,                        -- 영상 내 시작 시점(초)
    strategy        TEXT,                                 -- 매매기법 및 [기술적 조건: ...]
    stock_name      TEXT,                                 -- 언급 종목명 (예: 로보티즈)
    stock_code      TEXT,                                 -- 6자리 종목코드 (자동 변환 매핑)
    entry_price_1st REAL,                                 -- 1차 매수가
    entry_price_2nd REAL,                                 -- 2차 매수가
    target_price    REAL,                                 -- 목표가
    stop_loss_price REAL,                                 -- 손절가
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,   -- DB 생성 일시
    FOREIGN KEY (stock_code) REFERENCES stock_master(code)
);
```

---

## 2. 새로 추출된 '매매기법 및 심법' 데이터의 성격
기존 영상들은 "몇 분 몇 초에 로보티즈라는 종목을 얼마에 매수 관점으로 보았다"는 **[개별 종목 멘션(Stock Pick/Trade Recap)]** 위주였습니다.
하지만 최근 추출을 시작한 '매매기법 및 심법' 영상은 특정 1개 종목의 추천이 아니라, 영상 전체(20~30분)를 관통하는 **[전략/지식(Strategy / Knowledge Base)]** 데이터입니다:

```json
{
  "video_title": "S급 종목선정 기준 및 곱게 못 죽는 원리",
  "category": "매매 기법 및 심법",
  "core_philosophy": {
    "main_concept": "A급·S급 종목은 무한 상승이 아니라 밀렸을 때 곱게 못 죽고 2~3회 기술적 반등을 주는 종목임...",
    "key_analogies": [
      {"original_metaphor": "콜럼버스의 달걀", "intended_meaning": "알고 나면 기본기지만 발상 전환 전엔 모름"},
      {"original_metaphor": "직접 산에 가 나물 캐기", "intended_meaning": "스스로 통계 내는 노력의 중요성"},
      {"original_metaphor": "빵집 냄새와 맛있는 먹이", "intended_meaning": "세력이 개인을 유혹하는 매력적인 재료"}
    ],
    "psychological_warnings": "1+1=2 같은 마법의 변곡점 공식 환상 금지"
  },
  "quantitative_filters": {
    "volume_and_effort": "거래대금 3,000억~5,000억 원 이상 N회 연속 반복 터지는 빈도",
    "chart_position": "120일선 지지/저항, 피보나치, 3·4등분선, RSI 70 과매수 주의 vs RSI 30 과매도 분할매수"
  },
  "qualitative_filters": {
    "catalyst_analysis": "로봇(유니트리 상장, 피지컬 AI, 아틀라스, 옵티머스), 태양광, 원전 등",
    "market_regime_adaptation": "과열 시 현금화 대비, 투매 시 눈 딱 감고 분할 매수"
  },
  "actionable_rules": [
    {"rule_id": "RULE_1", "rule_type": "FILTER", "condition": "...", "action_or_mindset": "..."},
    {"rule_id": "RULE_2", "rule_type": "EXECUTION", "condition": "...", "action_or_mindset": "..."},
    {"rule_id": "RULE_3", "rule_type": "RISK", "condition": "...", "action_or_mindset": "..."},
    {"rule_id": "RULE_4", "rule_type": "MINDSET", "condition": "...", "action_or_mindset": "..."},
    {"rule_id": "RULE_5", "rule_type": "RESEARCH", "condition": "...", "action_or_mindset": "..."}
  ]
}
```

---

## 3. 컬럼별 충돌 분석 (기존 단일 테이블에 넣으려 할 때의 문제점)

기존 `youtube_mentions` 테이블에 기법 데이터를 넣으려고 대조해 보니 아래와 같은 심각한 비대칭(Sparse)이 발생합니다:

| 컬럼명 | [종목복기/테마분석] 영상 | [매매기법 및 심법] 영상 | 충돌 및 비대칭 현상 |
| :--- | :--- | :--- | :--- |
| `stock_name`, `stock_code` | `로보티즈`, `108490` | **`NULL`** | 특정 종목 추천이 아니므로 코드가 비어버림 |
| `time_start_sec` | `253.8` (초) | **`0.0` 또는 모호함** | 영상 전체(25분)에 걸친 강의라 특정 초 지정 불가 |
| `entry_price_1st`, `target_price`, `stop_loss_price` | `15,000원`, `18,000원` | **`NULL` (100% 미사용)** | 기법은 가격(원)이 아니라 조건(피보나치 0.382, RSI 30)임 |
| 비유 6종, 정량/정성 필터, 5대 룰 | 해당 없음 | **들어갈 컬럼이 없음** | 기존 컬럼에 자리가 없어 `master_json` 텍스트 컬럼에 통째로 우겨넣어야 함 |

---

## 4. 고민 중인 2가지 아키텍처 대안

### [방안 A] 실용주의 단일 테이블 (`youtube_mentions` 1개로 통합)
* **방식**: 기존 테이블에 `category TEXT`와 `master_json TEXT` 2개 컬럼만 추가하여 종목 멘션과 기법 데이터를 모두 한 테이블에 넣음.
* **장점**: 
  - 테이블이 딱 1개라 파이썬 봇이나 쿼리 작성 시 단일 테이블만 바라보면 됨.
  - 기존 시스템과의 연동 코드를 거의 안 고쳐도 됨.
* **단점**: 
  - 기법 데이터는 가격 컬럼 4개와 종목코드 컬럼이 100% `NULL`로 남아 테이블이 지저분해짐(Sparse Table).
  - 기법 데이터의 핵심 정보는 결국 `master_json`이라는 통문자열(JSON) 컬럼에 의존해야 함.

### [방안 B] 성격 분리 2개 테이블 (단일 DB 파일 `quant_market.db` 내 공존)
* **방식**: 같은 DB 파일 안에 성격이 다른 2개의 테이블로 명확히 분리:
  1. `youtube_mentions` (기존 유지): 종목명, 종목코드, 타임스탬프, 호가(가격) 중심의 **실제 종목 멘션/복기 전용**
  2. `youtube_strategies` (신설): 영상ID, 카테고리, 비유, 정량필터, 정성필터, 5대 룰 중심의 **순수 기법/전략 지식 전용**
* **장점**:
  - 기법 테이블에는 쓸데없는 가격/호가 컬럼이 없고, 종목 멘션 테이블에는 거대한 전략 JSON이 섞이지 않아 **NULL 낭비가 0%**임.
  - 두 데이터의 스키마 정체성이 완벽히 분리되어 깔끔함.
  - 필요할 때 `video_id`로 두 테이블을 JOIN하면 "이 기법 영상에서 실제로 언급된 종목 목록"을 쉽게 연결할 수 있음.
* **단점**:
  - 테이블이 1개가 아니라 2개가 됨.

---

## 5. 질문 사항
1. 퀀트 트레이딩 봇 연동 및 데이터 분석 관점에서 **[방안 A (단일 테이블 통합)]**와 **[방안 B (성격별 2개 테이블 분리)]** 중 어떤 아키텍처가 실무적으로 더 우월한가요?
2. 방안 A처럼 가격 컬럼이 대량으로 `NULL`이 발생하는 구조를 감수하고라도 단일 테이블로 가는 것이 편의상 이득인가요, 아니면 방안 B처럼 테이블을 2개로 쪼개는 것이 향후 확장성(백테스팅, 룰 엔진 연동)에 훨씬 유리한가요?
3. 당신이 시니어 데이터 엔지니어 / 퀀트 아키텍트라면 이 상황에서 어떤 최종 구조를 추천하시겠습니까?
