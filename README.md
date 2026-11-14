# Time Science – Character Report API

## Parent closing note
Mobile PDFs requested with `text_source: "child"` now end with a calming blue-tinted
"A Note to Parents" card after the final topic. The card has generous padding and a
corporate-blue left accent. Adult (`text_source: "report"`) and desktop PDFs are unchanged.
Copy this archive over the existing repository, run `python -m unittest discover -s tests`,
then commit, push and redeploy Render.

## Authorized saved-gender fallback
When `gender` is blank, null or omitted and `client_id` is supplied, the report API
retrieves `client_details.gender` before generating traits, JSON or either PDF layout.
Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` on Render (the project's public anon key,
not its service-role key). `DATABASE_URL` alone does not enable this lookup.
Send `Authorization: Bearer <signed-in user's Supabase access token>` and a UUID
`client_id` in the request body. The existing `X-API-Key`, if configured, is still
required but does not grant access to saved clients.
The API validates the sign-in, calls `can_access_assigned_client` under that user's
identity, then reads only gender under the same identity and row-level security.
Owners, assigned professionals and staff retain the application's existing access
rules; a client ID alone never grants access. Invalid sign-in returns 401, inaccessible
or missing clients return 403, and configuration/network failures return 503 without
silently guessing gender. Explicit nonblank gender takes precedence and performs no
lookup. Guests without a client ID still get neutral wording when gender is omitted;
authorized clients with an empty/unknown saved gender also get neutral wording.
No frontend changes are required for existing explicit-gender requests. To use this
fallback, callers must send both the saved client ID and their current user token.
Run `python -m unittest discover -s tests` after updating and redeploy Render.

## Gender-aware pronoun update
Copy this archive over your existing repository, commit and push to redeploy Render.
`ReportRequest` now accepts optional `gender` (`male`/`female`, with `boy`/`girl` also accepted).
Before JSON traits or either PDF layout are produced, generic pairs such as `he or she`,
`his/her`, `him or her`, and `himself or herself` become natural gender-specific wording.
Blank, omitted or unknown values use singular `they/their/them`, including common verb
agreement (`they are`, `they have`). Standalone pronouns are not changed because they may
refer to another person. No tag spreadsheet columns or saved report text are modified.

## Report section update
Copy this archive over your existing repository, commit and push to redeploy Render.
The app has added `client_tag_mappings.report_section` and copied existing Section names
once. This version reads **only Report section** for PDF/JSON headings and `/report/api/topics`.
Original hierarchy Section edits no longer change report headings. Blank Report section
values group under `Others`, never fall back to the hierarchy. Topic request selections
must use the new Report section names. Both child and adult reports share these headings.
Keep `DATABASE_URL` set for live values; the existing 60-second refresh still applies.
Spreadsheet headers: `Tag ID`, `Report section`, `Summary Title`, `Report text`, `Child report`.
Omitted spreadsheet columns preserve their saved values.

## Summary title update
Deploy this version after copying it into your existing repository. The live database
loader now reads `client_tag_mappings.summary_title`, shared by child and adult reports.
The app migration already adds that column. Keep `DATABASE_URL` set on Render so edits
arrive after the existing rule refresh interval (60 seconds by default).
Each JSON trait returns `summary_title` separately from `text`. PDFs render the title
and colon in bold inline at the body font size, with unchanged line spacing and reserved
right-side badge space. Blank titles fall back to the first three words of the tag's
display name; set an editorial 2–3 word Summary Title for best results. Body-text ranking,
deduplication, report source selection and accuracy codes are unchanged.
Run regression tests with `python -m unittest discover -s tests`.

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
