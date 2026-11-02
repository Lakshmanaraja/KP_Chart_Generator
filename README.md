# Time Science – Character Report API

Standalone Python (FastAPI) service that turns birth details into the phone-friendly
Character Assessment Report PDF (or JSON traits), using the same rules as timescience.org.

## Run
```bash
cp .env.example .env          # set API_KEYS
docker compose up --build     # http://localhost:8000/docs
```
Without Docker: `pip install -r requirements.txt && uvicorn app.main:app --reload`

## Endpoints
| Method | Path | Result |
|---|---|---|
| GET  | /health | status + rule count |
| GET  | /api/v1/topics | available topics |
| POST | /api/v1/report/character | PDF download (`?format=json` for JSON) |
| POST | /api/v1/report/character/traits | JSON sections for partner apps |
| POST | /api/v1/admin/reload-rules | reload rules (after DB changes) |

```bash
curl -X POST http://localhost:8000/api/v1/report/character \
  -H "X-API-Key: partner-key-1" -H "Content-Type: application/json" \
  -d '{"name":"Asha Kumar","date_of_birth":"1990-05-21","time_of_birth":"14:30:00",
       "latitude":13.0827,"longitude":80.2707,"timezone":5.5,"place":"Chennai"}' \
  -o report.pdf
```
Optional fields: `topics` (explicit list – overrides default exclusions of Industry,
Partner/Marriage, Sleep), `extra_tags` (verified tag names), `chart` (pre-computed KP chart).

## How it works
1. **Chart** – `app/chart_client.py` calls the KP chart service (houses + planets, cached, retried).
2. **Matching** – `app/engine/matcher.py`: columns PL, NL, SU, SS, SK (planets), DA, BH, AN, SN (cusps),
   DT (DA transit). AND/OR rules, NOT pairs, multi-bhava combinations within one cusp column.
3. **Ranking** – `app/engine/ranker.py`: tier PL=1, BH/SU=2, DA/NL=3, DT=4, AN/SS=5, SN/SK=6;
   sorted by bhava, tier, section order; duplicate sentences kept only at their best tier;
   codes like P1, PS1, PL1, PLT1.
4. **PDF** – `app/pdf/mobile_report.py`: 95×200 mm pages – cover with author/contact links,
   legend page, colored topic cards with code pills.

## Rules data
`app/data/tag_mappings_seed.json` is a snapshot of all active rules that have Report Text.
Re-export it after editing rules, or set `DATABASE_URL` to read them live.

## Tests
`pytest` (offline, synthetic chart).
