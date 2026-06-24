"""
Vienna Eats - restaurant recommendation chatbot backend.

Flow per user message:
  1. Claude parses the free-text query into structured Places filters.
  2. We call Google Places Text Search (New) with those filters.
  3. Results come back sorted by rating; we attach price, address, a top review,
     and a Google Maps link for directions.
  4. Claude writes the natural-language answer over those results.

Runs in MOCK mode if GOOGLE_MAPS_API_KEY is not set, so you can test the whole
loop before turning on billing.
"""

import os
import re
import json
import time
import httpx
from collections import deque, defaultdict
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

# ---- config ----
GOOGLE_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-6"

# --- guardrail config (override via env on Render) ---
# Comma-separated list of allowed frontend origins. "*" only for local dev.
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
# Max requests per IP per rolling window.
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "20"))
RATE_WINDOW = int(os.environ.get("RATE_WINDOW_SECONDS", "60"))
MAX_MESSAGE_LEN = 300

# Vienna city centre, used as the default location bias.
VIENNA_LAT, VIENNA_LNG = 48.2082, 16.3738

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# Only request the fields we use. This list also controls how much Google bills.
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
    "places.googleMapsUri",
    "places.currentOpeningHours.openNow",
    "places.reviews",
    "places.primaryType",
])

app = FastAPI(title="What's Good Vienna")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # set ALLOWED_ORIGINS env to your domain in prod
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Simple in-memory per-IP rate limiter. Fine for a single Render instance;
# for multiple instances you'd move this to Redis.
_hits: dict[str, deque] = defaultdict(deque)


def _rate_limited(ip: str) -> bool:
    now = time.time()
    dq = _hits[ip]
    while dq and dq[0] < now - RATE_WINDOW:
        dq.popleft()
    if len(dq) >= RATE_LIMIT:
        return True
    dq.append(now)
    return False


# Cheap pre-filter so the endpoint isn't used as a free general-purpose chatbot.
# Blocks obvious injection phrases and requires the message to look food-related.
_INJECTION = re.compile(
    r"ignore (the |your |all )?(previous |above )?(instruction|prompt)|"
    r"system prompt|you are now|act as|disregard",
    re.I,
)
_FOOD_HINT = re.compile(
    r"eat|food|restaurant|cafe|coffee|drink|bar|meal|lunch|dinner|breakfast|brunch|"
    r"spicy|mild|sweet|halal|vegan|vegetarian|cuisine|dish|hotpot|sushi|pizza|kebab|"
    r"curry|noodle|dessert|bakery|hungry|cheap|budget|price|rating|near|open|"
    r"indian|bangladeshi|georgian|thai|chinese|italian|turkish|arab|asian|wine|beer",
    re.I,
)


class ChatRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def _check(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message is empty.")
        if len(v) > MAX_MESSAGE_LEN:
            raise ValueError(f"Message too long (max {MAX_MESSAGE_LEN} characters).")
        return v


# Map Google's price enum to euro bands so the model can talk about them.
PRICE_LABELS = {
    "PRICE_LEVEL_INEXPENSIVE": "€ (budget, roughly under €15)",
    "PRICE_LEVEL_MODERATE": "€€ (mid, roughly €15-35)",
    "PRICE_LEVEL_EXPENSIVE": "€€€ (€35-60)",
    "PRICE_LEVEL_VERY_EXPENSIVE": "€€€€ (€60+)",
}


# ---------------------------------------------------------------------------
# Step 1: parse the user's free text into structured filters using Claude.
# ---------------------------------------------------------------------------
PARSE_SYSTEM = """You convert a diner's request into a JSON filter for the Google Places API.
Return ONLY a JSON object, no prose, no backticks. Schema:
{
  "text_query": str,        // a clean search string, e.g. "spicy halal indian restaurant Vienna"
  "min_rating": float|null, // 0-5, set only if the user asks for "best"/"top"/"highly rated"
  "max_price_level": int|null, // 1=budget(<~15e) 2=mid 3=expensive 4=very. Set from price hints like "under 15", "cheap"
  "open_now": bool,         // true only if user mentions "now"/"open"/"tonight"
  "rank_by": str            // "RELEVANCE" normally, "DISTANCE" if user says "near"/"nearby"/"closest"
}
Notes: "spicy", "mild", "sweet", "halal", "hotpot", cuisine names all go into text_query as keywords.
Always append "Vienna" to text_query if no city is named."""


async def parse_query(message: str) -> dict:
    if not ANTHROPIC_KEY:
        # Fallback parser so the app works without an LLM key during early testing.
        return {
            "text_query": f"{message} Vienna",
            "min_rating": 4.0 if any(w in message.lower() for w in ["best", "top"]) else None,
            "max_price_level": 1 if any(w in message.lower() for w in ["under 15", "cheap", "budget"]) else None,
            "open_now": "now" in message.lower() or "tonight" in message.lower(),
            "rank_by": "DISTANCE" if "near" in message.lower() else "RELEVANCE",
        }
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 400,
        "system": PARSE_SYSTEM,
        "messages": [{"role": "user", "content": message}],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(ANTHROPIC_URL, json=payload, headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        })
    text = "".join(b.get("text", "") for b in r.json().get("content", []))
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text_query": f"{message} Vienna", "min_rating": None,
                "max_price_level": None, "open_now": False, "rank_by": "RELEVANCE"}


# ---------------------------------------------------------------------------
# Step 2: call Google Places (or return mock data in MOCK mode).
# ---------------------------------------------------------------------------
async def search_places(filters: dict) -> list[dict]:
    if not GOOGLE_KEY:
        return _mock_places(filters)

    body = {
        "textQuery": filters["text_query"],
        "maxResultCount": 10,
        "rankPreference": filters.get("rank_by", "RELEVANCE"),
        "locationBias": {"circle": {
            "center": {"latitude": VIENNA_LAT, "longitude": VIENNA_LNG},
            "radius": 8000.0,
        }},
        "languageCode": "en",
        "regionCode": "AT",
    }
    if filters.get("min_rating"):
        body["minRating"] = filters["min_rating"]
    if filters.get("open_now"):
        body["openNow"] = True
    if filters.get("max_price_level"):
        levels = ["PRICE_LEVEL_INEXPENSIVE", "PRICE_LEVEL_MODERATE",
                  "PRICE_LEVEL_EXPENSIVE", "PRICE_LEVEL_VERY_EXPENSIVE"]
        body["priceLevels"] = levels[:filters["max_price_level"]]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(PLACES_URL, json=body, headers={
            "X-Goog-Api-Key": GOOGLE_KEY,
            "X-Goog-FieldMask": FIELD_MASK,
            "Content-Type": "application/json",
        })
    places = r.json().get("places", [])
    return [_normalise(p) for p in places]


def _confidence(rating_count: int, rating: float | None) -> str:
    """
    A trust signal, not a quality signal. Borrows the calibration logic from the
    knowledge-distillation lab: a 4.9 from 11 reviews is a high-variance estimate,
    a 4.4 from 4,000 is a settled one. Below the low threshold the bot should hedge
    rather than assert, the same "don't deploy a confident answer below threshold"
    rule from the Scenario B coverage table.
    """
    if rating is None or rating_count == 0:
        return "unrated"
    if rating_count >= 500:
        return "high"
    if rating_count >= 80:
        return "medium"
    return "low"


def _normalise(p: dict) -> dict:
    reviews = p.get("reviews", [])
    top_review = ""
    if reviews:
        top_review = reviews[0].get("text", {}).get("text", "")[:240]
    rating = p.get("rating")
    rating_count = p.get("userRatingCount", 0)
    return {
        "name": p.get("displayName", {}).get("text", "Unknown"),
        "rating": rating,
        "rating_count": rating_count,
        "confidence": _confidence(rating_count, rating),
        "price": PRICE_LABELS.get(p.get("priceLevel", ""), "price not listed"),
        "address": p.get("formattedAddress", ""),
        "open_now": p.get("currentOpeningHours", {}).get("openNow"),
        "maps_url": p.get("googleMapsUri", ""),
        "top_review": top_review,
    }


def _rank(places: list[dict]) -> list[dict]:
    # Sort best-to-worst by rating, breaking ties by how many ratings (trust).
    # A Bayesian shrinkage toward the mean would be more correct, but tie-break
    # on count is a cheap stand-in that avoids ranking a 4.9-from-9 above a 4.6-from-3000.
    return sorted(places, key=lambda x: (x.get("rating") or 0, x.get("rating_count") or 0),
                  reverse=True)


# ---------------------------------------------------------------------------
# Step 3: Claude writes the answer over the ranked results.
# ---------------------------------------------------------------------------
ANSWER_SYSTEM = """You are a friendly Vienna food guide. You are given the user's request and a
ranked list of restaurants (already sorted best rating first). Recommend the top few that fit.
For each: name, rating with count, price band, one line on why, the address, and the maps link
for directions. Be concise and warm, a little playful is fine.

Use the "confidence" field honestly:
- "high"/"medium": state the rating plainly.
- "low": the rating rests on few reviews, so add a short hedge like "(only a handful of ratings)".
- "unrated": say it has no ratings yet.

Important: traits like halal, spicy level, or specific cuisine are inferred from names and
reviews, not verified facts. When you mention them, phrase as "looks halal based on reviews,
worth confirming" rather than stating them as certain. Never present an inferred trait as
guaranteed. If the list is empty, say so plainly and suggest loosening a filter.
Do not invent places or details not in the data."""


async def write_answer(message: str, places: list[dict]) -> str:
    if not ANTHROPIC_KEY:
        return _plain_answer(places)
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1000,
        "system": ANSWER_SYSTEM,
        "messages": [{"role": "user", "content":
            f"User asked: {message}\n\nRanked results:\n{json.dumps(places, indent=2)}"}],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(ANTHROPIC_URL, json=payload, headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        })
    return "".join(b.get("text", "") for b in r.json().get("content", []))


def _plain_answer(places: list[dict]) -> str:
    if not places:
        return "No matches found. Try loosening the price or cuisine filter."
    lines = []
    for p in places[:5]:
        if p["rating"]:
            hedge = " (few ratings, take with a grain of salt)" if p.get("confidence") == "low" else ""
            r = f"{p['rating']}\u2605 ({p['rating_count']}){hedge}"
        else:
            r = "no ratings yet"
        lines.append(f"- {p['name']} - {r} - {p['price']}\n  {p['address']}\n  {p['maps_url']}")
    return "Here are the top matches:\n\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
@app.get("/")
def health():
    mode = "LIVE" if GOOGLE_KEY else "MOCK"
    return {"status": "ok", "mode": mode}


@app.get("/app")
def ui():
    return FileResponse("static/index.html")


@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    # 1. rate limit per IP to protect the API bill
    ip = request.client.host if request.client else "unknown"
    if _rate_limited(ip):
        raise HTTPException(status_code=429,
                            detail="Slow down a little. Try again in a minute.")

    # 2. block obvious prompt-injection attempts
    if _INJECTION.search(req.message):
        return {"answer": "I only help with finding places to eat and drink in Vienna. "
                          "Ask me about food, cuisines, prices, or areas.",
                "filters": {}, "results": []}

    # 3. keep it on-topic so it isn't used as a free general chatbot
    if not _FOOD_HINT.search(req.message):
        return {"answer": "I'm your Vienna food guide. Tell me a taste, cuisine, price, "
                          "or area and I'll find spots. Try 'spicy halal under 15 euro'.",
                "filters": {}, "results": []}

    filters = await parse_query(req.message)
    places = _rank(await search_places(filters))
    answer = await write_answer(req.message, places)
    return {"answer": answer, "filters": filters, "results": places}


# ---------------------------------------------------------------------------
def _mock_places(filters: dict) -> list[dict]:
    """Stand-in data so you can test the loop before enabling billing."""
    sample = [
        {"name": "Dilkhush", "rating": 4.6, "rating_count": 820,
         "price": PRICE_LABELS["PRICE_LEVEL_INEXPENSIVE"],
         "address": "Hofgasse 1, 1110 Wien", "open_now": True,
         "maps_url": "https://maps.google.com/?cid=1",
         "top_review": "Best Pakistani-style spicy curry in Vienna, very generous portions."},
        {"name": "Tewa Naschmarkt", "rating": 4.4, "rating_count": 1530,
         "price": PRICE_LABELS["PRICE_LEVEL_MODERATE"],
         "address": "Naschmarkt Stand 671, 1040 Wien", "open_now": True,
         "maps_url": "https://maps.google.com/?cid=2",
         "top_review": "Fresh, mildly spiced halal bowls, fast service at lunch."},
        {"name": "Der Wiener Deewan", "rating": 4.5, "rating_count": 4100,
         "price": PRICE_LABELS["PRICE_LEVEL_INEXPENSIVE"],
         "address": "Liechtensteinstrasse 10, 1090 Wien", "open_now": False,
         "maps_url": "https://maps.google.com/?cid=3",
         "top_review": "Pay-as-you-wish Pakistani buffet, reliably spicy and cheap."},
        # Deliberately low rating count to exercise the confidence hedge.
        {"name": "Dhaka Tang (new)", "rating": 4.9, "rating_count": 11,
         "price": PRICE_LABELS["PRICE_LEVEL_INEXPENSIVE"],
         "address": "Quellenstrasse 12, 1100 Wien", "open_now": True,
         "maps_url": "https://maps.google.com/?cid=4",
         "top_review": "Rare Bangladeshi spot, spicy and authentic, just opened."},
    ]
    # Compute the confidence tier the same way live results get it.
    for s in sample:
        s["confidence"] = _confidence(s["rating_count"], s["rating"])
    if filters.get("min_rating"):
        sample = [s for s in sample if s["rating"] >= filters["min_rating"]]
    return sample
