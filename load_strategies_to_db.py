import os
import sys
import json
import sqlite3

sys.stdout.reconfigure(encoding="utf-8")

db_path = r"E:\키움_rest_api\database\quant_market.db"
json_dir = r"E:\키움_rest_api\결과물"

if not os.path.exists(db_path):
    print(f"Error: Database file not found at {db_path}")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 외래키 활성화
cur.execute("PRAGMA foreign_keys = ON;")

json_files = [f for f in os.listdir(json_dir) if f.endswith(".json")]
print(f"Found {len(json_files)} strategy JSON files in {json_dir}")

loaded_count = 0
skipped_count = 0

for fname in sorted(json_files):
    fpath = os.path.join(json_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    vid = str(data.get("video_id", "")).strip()
    vtitle = data.get("video_title", "")
    category = data.get("category", "")
    
    # Check video_master
    cur.execute("SELECT count(*) FROM video_master WHERE video_id = ?;", (vid,))
    if cur.fetchone()[0] == 0:
        print(f"[SKIP] video_id {vid} ({fname}) does not exist in video_master!")
        skipped_count += 1
        continue
        
    core = data.get("core_philosophy", {})
    main_concept = core.get("main_concept", "")
    psychological_warnings = core.get("psychological_warnings", "")
    
    key_analogies = json.dumps(core.get("key_analogies", []), ensure_ascii=False) if "key_analogies" in core else None
    quant_filters = json.dumps(data.get("quantitative_filters", {}), ensure_ascii=False) if "quantitative_filters" in data else None
    qual_filters = json.dumps(data.get("qualitative_filters", {}), ensure_ascii=False) if "qualitative_filters" in data else None
    actionable_rules = json.dumps(data.get("actionable_rules", []), ensure_ascii=False) if "actionable_rules" in data else None
    
    cur.execute("""
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
    """, (
        vid,
        vtitle,
        category,
        main_concept,
        psychological_warnings,
        key_analogies,
        quant_filters,
        qual_filters,
        actionable_rules
    ))
    loaded_count += 1
    print(f"[OK] Loaded [{vid}] {vtitle[:30]}")

conn.commit()

# 검증 쿼리
cur.execute("SELECT count(*) FROM youtube_strategies;")
total_in_db = cur.fetchone()[0]

cur.execute("SELECT video_id, video_title, category FROM youtube_strategies ORDER BY video_id;")
rows = cur.fetchall()

print("\n" + "="*60)
print(f"DATABASE LOADING SUMMARY:")
print(f" - Loaded/Updated: {loaded_count} items")
print(f" - Skipped: {skipped_count} items")
print(f" - Total strategies in DB: {total_in_db} rows")
print("="*60)
print("\nCurrent Strategy List in DB:")
for r in rows:
    print(f"  [{r[0]}] ({r[2]}) {r[1][:35]}")

conn.close()
