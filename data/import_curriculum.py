"""
data/import_curriculum.py — Import 9-month curriculum words into VoodooBot DB.
Run once: python3 data/import_curriculum.py
"""
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = Path(__file__).parent.parent / "database" / "voodoo.db"

# Import the curriculum
sys.path.insert(0, str(Path(__file__).parent))
from curriculum_9months import CURRICULUM

MONTH_LEVEL = {
    4: "A2",  5: "A2",  6: "B1",
    7: "B1",  8: "B1",  9: "B2",
    10: "B2", 11: "B2", 12: "C1",
}

def run():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    inserted = 0
    skipped = 0

    for week in CURRICULUM:
        level = MONTH_LEVEL.get(week["month"], "A2")
        theme = week["theme"]
        for w in week["words"]:
            en   = w["en"].strip().lower()
            ua   = w["ua"].strip()
            ex   = w.get("example", "")
            try:
                cur.execute(
                    """INSERT OR IGNORE INTO words
                       (word, translation, level, theme, example_en)
                       VALUES (?,?,?,?,?)""",
                    (en, ua, level, theme, ex),
                )
                if cur.rowcount:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"  Error on {en!r}: {e}")

    con.commit()
    con.close()

    total = cur.lastrowid
    print(f"✅ Done: {inserted} words inserted, {skipped} duplicates skipped")
    print(f"   DB: {DB_PATH}")

if __name__ == "__main__":
    run()
