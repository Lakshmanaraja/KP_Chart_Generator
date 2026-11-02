"""Loads tag rules from the bundled JSON seed, or live from PostgreSQL when DATABASE_URL is set."""
import json
import os
from functools import lru_cache
from typing import List

SEED = os.path.join(os.path.dirname(__file__), "tag_mappings_seed.json")

SQL = """
SELECT m.tag, COALESCE(m.display_name, m.tag) AS display_name, m.pairs, m.display_order,
       m.match_mode, m.group_name, m.report_text, q.title AS section, q.bhava_no,
       COALESCE(q.section_order, 0) AS section_order
FROM client_tag_mappings m
LEFT JOIN kp_answer_options_v2 a ON a.client_tag_mapping_id = m.id
LEFT JOIN kp_questions_v2 q ON q.id = a.question_id
WHERE m.is_active AND trim(coalesce(m.report_text, '')) <> ''
"""


@lru_cache(maxsize=1)
def load_mappings() -> List[dict]:
    url = os.getenv("DATABASE_URL")
    if url:
        import psycopg  # optional dependency
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute(SQL)
            cols = [c.name for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    else:
        with open(SEED, encoding="utf-8") as f:
            rows = json.load(f)
    for r in rows:
        r.setdefault("is_active", True)
        if isinstance(r.get("pairs"), str):
            r["pairs"] = json.loads(r["pairs"])
    return rows


def reload_mappings():
    load_mappings.cache_clear()
    return load_mappings()
