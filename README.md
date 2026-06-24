# What's Good Vienna

A restaurant recommendation chatbot for Vienna. Ask in plain language
("spicy halal under €15 near me", "best hotpot", "Georgian food open now")
and get restaurants ranked best-rating-first, with price band, address,
a top review, and a Google Maps link for directions.

## How it works

Two LLM calls bracket one Places API call:

1. Claude parses your message into structured filters (keywords, price cap,
   min rating, rank-by-distance, open-now).
2. Google Places Text Search (New) returns matching Vienna restaurants.
3. Results are ranked by rating, then by number of ratings (ties).
4. Claude writes the answer over those results.

If `GOOGLE_MAPS_API_KEY` is missing it runs in **MOCK mode** with sample data,
so you can test the whole loop before turning on billing. Same trick for
`ANTHROPIC_API_KEY` (a keyword-based fallback parser kicks in).

## Run locally

    pip install -r requirements.txt
    uvicorn app.main:app --reload

Open http://localhost:8000/app

## Deploy to Render

1. Push this folder to a GitHub repo.
2. Render -> New Web Service -> point at the repo. `render.yaml` is read automatically.
3. Add the two env vars (`GOOGLE_MAPS_API_KEY`, `ANTHROPIC_API_KEY`) in the dashboard.
4. The chat UI lives at `https://your-service.onrender.com/app`.

## Google setup (the part that costs money)

- Create a Google Cloud project, enable **Places API (New)**, add a billing card.
- The free monthly credit covers light use. A public app can exceed it.
- In Cloud Console set a **quota cap** and a **budget alert** so you can't be surprised.
- The `FIELD_MASK` in `main.py` controls which fields you pay for. Keep it tight.

## Guardrails (added)

The `/chat` endpoint has basic protection so it can't be abused or run up your bill:

- **Rate limit:** per-IP, default 20 requests / 60s. Tune with `RATE_LIMIT` and
  `RATE_WINDOW_SECONDS`. In-memory, so it resets on restart and is per-instance.
  For multiple Render instances, move the counter to Redis.
- **Input cap:** messages over 300 characters are rejected (422) before any paid call.
- **Topic guard:** messages with no food-related word get a polite redirect instead
  of hitting the LLM or Places API, so the endpoint isn't a free general chatbot.
- **Injection filter:** common "ignore your instructions" phrasings are refused.
- **CORS:** set `ALLOWED_ORIGINS` to your domain in production (defaults to `*` for
  local dev only).

These run *before* the paid Anthropic and Google calls, so blocked requests cost nothing.
Still set a Google Cloud budget cap as a final backstop.

## Known limits (read before you scale this)

- **TOS:** Google restricts caching/storing most Places fields. This app queries
  live per request and links back to Maps, which is the compliant pattern. Do not
  build a stored copy of their ratings/reviews.
- **"spicy" / "halal" are not API fields.** They're passed as free-text keywords,
  so accuracy depends on what shows up in names and reviews. For reliable spice
  level and halal certification you need your own curated tags (the Option C
  upgrade): keep a small table of place_id -> {spice, halal} and merge it in
  after the Places call.
- **Thin-data cuisines** (Bangladeshi, Georgian) have fewer reviews, so results
  there are weaker. That's exactly the segment a curated layer would fix.

## Next steps

- Add a `curated.json` of place_id -> tags and merge in `_normalise`.
- Add conversation memory (pass prior turns) for follow-ups like "cheaper ones".
- Cache the *place_id list* per query for a short window to cut cost (allowed),
  but re-fetch live details.
