from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import math
import os

app = FastAPI(title="What's Good Vienna?", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load data
DATA_PATH = os.path.join(os.path.dirname(__file__), "vienna_restaurants.json")
with open(DATA_PATH, "r") as f:
    RESTAURANTS = json.load(f)

PRICE_MAP = {"€": 1, "€€": 2, "€€€": 3}

class ChatQuery(BaseModel):
    query: str
    user_lat: Optional[float] = 48.2082
    user_lon: Optional[float] = 16.3738

class RestaurantResult(BaseModel):
    id: int
    name: str
    cuisine: str
    city: str
    address: str
    lat: float
    lon: float
    price_level: str
    rating: float
    review_count: int
    taste_tags: List[str]
    food_type: List[str]
    diet: List[str]
    vibe: List[str]
    use_case: List[str]
    opening_hours: str
    distance_km: float
    match_score: float
    ai_explanation: str
    phone: str
    website: str
    source: str

class ChatResponse(BaseModel):
    results: List[RestaurantResult]
    understood_filters: dict
    total_matches: int


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def parse_query(query: str) -> dict:
    q = query.lower()
    filters = {
        "cuisine": None, "taste_tags": [], "food_type": [],
        "diet": [], "vibe": [], "use_case": [],
        "max_price": None, "min_price": None, "location_hint": None
    }

    # Cuisine
    cuisine_map = {
        "Indian": ["indian", "curry", "biryani", "masala", "tandoori", "indisch"],
        "Vietnamese": ["vietnamese", "vietnamesisch", "pho", "banh mi", "bun"],
        "Chinese": ["chinese", "chinesisch", "dim sum", "dumpling", "sichuan", "peking duck", "hot pot"],
        "Thai": ["thai", "thailändisch", "pad thai", "tom yum"],
        "Japanese": ["japanese", "japanisch", "sushi", "ramen", "tempura"],
        "Korean": ["korean", "koreanisch", "bibimbap", "kbbq", "korean bbq"],
        "Turkish": ["turkish", "türkisch", "kebab", "kebap", "döner"],
        "Lebanese": ["lebanese", "libanesisch", "falafel", "hummus", "shawarma"],
        "Israeli": ["israeli", "israelisch"],
        "Persian": ["persian", "iranian", "iranisch"],
        "French": ["french", "französisch", "croissant", "baguette"],
        "Austrian": ["austrian", "österreichisch", "wiener", "schnitzel", "tafelspitz"],
        "Italian": ["italian", "italienisch", "pizza", "pasta", "risotto"],
        "Mexican": ["mexican", "mexican", "taco", "burrito", "nachos", "enchilada"],
        "Burger": ["burger", "hamburger", "cheeseburger"],
        "Seafood": ["seafood", "fish", "fisch", "shrimp", "oyster"],
        "Vegetarian": ["vegetarian", "vegan", "plant-based"],
        "Cafe": ["cafe", "coffee", "kaffee", "espresso", "cappuccino", "café"],
        "Ice Cream": ["ice cream", "eis", "gelato"],
        "International": ["international", "fusion"]
    }
    for cuisine, kws in cuisine_map.items():
        for kw in kws:
            if kw in q:
                filters["cuisine"] = cuisine
                break
        if filters["cuisine"]: break

    # Taste tags
    taste_map = {
        "spicy": ["spicy", "scharf", "hot", "chili", "pepper", "fire"],
        "mild": ["mild", "not spicy", "gentle", "subtle", "light"],
        "sweet": ["sweet", "süß", "dessert", "cake", "pastry", "chocolate", "sugar"],
        "sour": ["sour", "sauer", "tangy", "citrus", "lemon"],
        "umami": ["umami", "savory", "rich", "deep flavor"],
        "creamy": ["creamy", "rich", "smooth", "buttery"],
        "fried": ["fried", "crispy", "crunchy", "deep fried"],
        "soup": ["soup", "suppe", "broth", "pho", "ramen"],
        "curry": ["curry", "masala", "biryani"]
    }
    for tag, kws in taste_map.items():
        for kw in kws:
            if kw in q:
                if tag not in filters["taste_tags"]: filters["taste_tags"].append(tag)
                break

    # Food type
    food_map = {
        "rice": ["rice", "reis", "pilaf", "biryani"],
        "noodles": ["noodles", "nudeln", "pasta", "ramen", "pho", "pad thai"],
        "soup": ["soup", "suppe", "broth", "pho", "ramen", "tom yum"],
        "curry": ["curry", "masala"],
        "dessert": ["dessert", "sweet", "cake", "ice cream", "pastry"],
        "naan": ["naan", "bread", "roti"]
    }
    for ft, kws in food_map.items():
        for kw in kws:
            if kw in q:
                if ft not in filters["food_type"]: filters["food_type"].append(ft)
                break

    # Diet
    diet_map = {
        "halal": ["halal", "muslim", "islamic"],
        "vegetarian": ["vegetarian", "veggie", "meat-free"],
        "vegan": ["vegan", "plant-based", "dairy-free"]
    }
    for d, kws in diet_map.items():
        for kw in kws:
            if kw in q:
                if d not in filters["diet"]: filters["diet"].append(d)
                break

    # Vibe
    vibe_map = {
        "cafe": ["cafe", "coffee", "cozy", "warm"],
        "casual": ["casual", "relaxed", "easy", "simple"],
        "romantic": ["romantic", "date", "intimate", "candlelight"],
        "family": ["family", "kid-friendly", "children", "kids"],
        "cheap eats": ["cheap", "budget", "affordable", "inexpensive"]
    }
    for v, kws in vibe_map.items():
        for kw in kws:
            if kw in q:
                if v not in filters["vibe"]: filters["vibe"].append(v)
                break

    # Use case
    use_map = {
        "date": ["date", "romantic", "anniversary", "special occasion"],
        "study cafe": ["study", "work", "laptop", "wifi", "quiet", "cozy", "read"],
        "quick lunch": ["quick lunch", "lunch", "fast", "work lunch", "business lunch"],
        "family": ["family", "kid-friendly", "children", "kids", "group"],
        "cheap eats": ["cheap eats", "budget", "affordable", "student", "cheap"],
        "takeaway": ["takeaway", "take-out", "to-go", "delivery", "grab"],
        "late-night": ["late-night", "late night", "open late", "midnight", "after hours"]
    }
    for u, kws in use_map.items():
        for kw in kws:
            if kw in q:
                if u not in filters["use_case"]: filters["use_case"].append(u)
                break

    # Price
    if "under €15" in q or "cheap" in q or "budget" in q or "student" in q:
        filters["max_price"] = "€"
    elif "under €25" in q or "moderate" in q or "mid-range" in q:
        filters["max_price"] = "€€"
    elif "expensive" in q or "fancy" in q or "fine dining" in q or "special" in q:
        filters["min_price"] = "€€€"

    if "€€€" in q: filters["min_price"] = "€€€"
    elif "€€" in q and "€€€" not in q: 
        filters["max_price"] = "€€"; filters["min_price"] = "€€"
    elif "€" in q and "€€" not in q: filters["max_price"] = "€"

    return filters


def score_restaurant(r, filters, user_lat, user_lon):
    score = 0.0
    reasons = []

    dist = haversine(user_lat, user_lon, r["lat"], r["lon"])
    distance_score = max(0, 1 - (dist / 5))
    score += distance_score * 15

    # Cuisine
    if filters["cuisine"] and filters["cuisine"].lower() == r["cuisine"].lower():
        score += 25
        reasons.append(f"Cuisine: {r['cuisine']}")

    # Taste tags
    taste_matches = [t for t in filters["taste_tags"] if t in r["taste_tags"]]
    if taste_matches:
        score += len(taste_matches) * 12
        reasons.append(f"Taste: {', '.join(taste_matches)}")

    # Food type
    food_matches = [f for f in filters["food_type"] if f in r["food_type"]]
    if food_matches:
        score += len(food_matches) * 10
        reasons.append(f"Food: {', '.join(food_matches)}")

    # Diet
    diet_matches = [d for d in filters["diet"] if d in r["diet"]]
    if diet_matches:
        score += len(diet_matches) * 15
        reasons.append(f"Diet: {', '.join(diet_matches)}")

    # Vibe
    vibe_matches = [v for v in filters["vibe"] if v in r["vibe"]]
    if vibe_matches:
        score += len(vibe_matches) * 8
        reasons.append(f"Vibe: {', '.join(vibe_matches)}")

    # Use case
    use_matches = [u for u in filters["use_case"] if u in r["use_case"]]
    if use_matches:
        score += len(use_matches) * 10
        reasons.append(f"Perfect for: {', '.join(use_matches)}")

    # Price
    if filters["max_price"]:
        if PRICE_MAP[r["price_level"]] <= PRICE_MAP[filters["max_price"]]:
            score += 10
            reasons.append(f"Budget: {r['price_level']}")
        else:
            score -= 25
    if filters["min_price"]:
        if PRICE_MAP[r["price_level"]] >= PRICE_MAP[filters["min_price"]]:
            score += 10
            reasons.append(f"Price: {r['price_level']}")
        else:
            score -= 15

    # Rating & popularity
    score += (r["rating"] - 3.0) * 6
    if r["rating"] >= 4.3: reasons.append(f"Top rated ({r['rating']}/5)")
    score += min(r["review_count"] / 400, 6)

    # No filters fallback
    if not any([filters["cuisine"], filters["taste_tags"], filters["food_type"], 
                filters["diet"], filters["vibe"], filters["use_case"], filters["max_price"]]):
        score += r["rating"] * 6 + distance_score * 12

    return score, dist, reasons


def generate_explanation(r, filters, reasons, dist):
    parts = []

    # Opening
    if filters["cuisine"] and r["cuisine"].lower() == filters["cuisine"].lower():
        parts.append(f"A top-rated {r['cuisine']} spot")
    else:
        parts.append(f"A well-loved {r['cuisine']} restaurant")

    # Distance
    if dist < 0.5: parts.append("just a short walk away")
    elif dist < 1.5: parts.append(f"about {dist:.1f} km from you")
    else: parts.append(f"{dist:.1f} km away")

    # Key features
    features = []
    if "spicy" in r["taste_tags"]: features.append("known for bold, spicy flavors")
    if "curry" in r["taste_tags"]: features.append("famous for rich curries")
    if "soup" in r["taste_tags"]: features.append("hearty soups")
    if "sweet" in r["taste_tags"]: features.append("amazing sweet treats")
    if "halal" in r["diet"]: features.append("halal-certified")
    if "vegan" in r["diet"]: features.append("fully vegan menu")
    if "vegetarian" in r["diet"]: features.append("great vegetarian options")
    if "cafe" in r["vibe"]: features.append("perfect cafe atmosphere")
    if "romantic" in r["vibe"]: features.append("romantic ambiance")
    if "family" in r["vibe"]: features.append("family-friendly")
    if "study cafe" in r["use_case"]: features.append("quiet and study-friendly")
    if "date" in r["use_case"]: features.append("ideal for dates")
    if "late-night" in r["use_case"]: features.append("open late")
    if "takeaway" in r["use_case"]: features.append("quick takeaway")

    if features: parts.append("— " + ", ".join(features))

    # Price & rating
    parts.append(f"Rated {r['rating']}/5 with {r['review_count']} reviews. Price: {r['price_level']}.")

    return " ".join(parts)


@app.get("/")
def root():
    return {"message": "What's Good Vienna? API v2", "restaurants": len(RESTAURANTS)}


@app.post("/chat", response_model=ChatResponse)
def chat(query_data: ChatQuery):
    filters = parse_query(query_data.query)

    scored = []
    for r in RESTAURANTS:
        score, dist, reasons = score_restaurant(r, filters, query_data.user_lat, query_data.user_lon)
        scored.append((score, dist, reasons, r))

    scored.sort(key=lambda x: x[0], reverse=True)

    top_results = []
    for score, dist, reasons, r in scored[:5]:
        if score > 0:
            explanation = generate_explanation(r, filters, reasons, dist)
            top_results.append(RestaurantResult(
                id=r["id"], name=r["name"], cuisine=r["cuisine"], city=r["city"],
                address=r["address"], lat=r["lat"], lon=r["lon"],
                price_level=r["price_level"], rating=r["rating"], review_count=r["review_count"],
                taste_tags=r["taste_tags"], food_type=r["food_type"], diet=r["diet"],
                vibe=r["vibe"], use_case=r["use_case"], opening_hours=r["opening_hours"],
                distance_km=round(dist, 2), match_score=round(score, 1),
                ai_explanation=explanation, phone=r["phone"], website=r["website"], source=r["source"]
            ))

    return ChatResponse(
        results=top_results,
        understood_filters=filters,
        total_matches=len([s for s in scored if s[0] > 0])
    )


@app.get("/restaurants")
def get_restaurants(
    cuisine: Optional[str] = None, taste: Optional[str] = None,
    food_type: Optional[str] = None, diet: Optional[str] = None,
    vibe: Optional[str] = None, use_case: Optional[str] = None,
    max_price: Optional[str] = None, min_rating: Optional[float] = None
):
    results = RESTAURANTS
    if cuisine: results = [r for r in results if r["cuisine"].lower() == cuisine.lower()]
    if taste: results = [r for r in results if taste in r["taste_tags"]]
    if food_type: results = [r for r in results if food_type in r["food_type"]]
    if diet: results = [r for r in results if diet in r["diet"]]
    if vibe: results = [r for r in results if vibe in r["vibe"]]
    if use_case: results = [r for r in results if use_case in r["use_case"]]
    if max_price: results = [r for r in results if PRICE_MAP[r["price_level"]] <= PRICE_MAP[max_price]]
    if min_rating: results = [r for r in results if r["rating"] >= min_rating]
    return {"count": len(results), "restaurants": results}


@app.get("/metadata")
def get_metadata():
    return {
        "cuisines": sorted(set(r["cuisine"] for r in RESTAURANTS)),
        "taste_tags": sorted(set(t for r in RESTAURANTS for t in r["taste_tags"])),
        "food_types": sorted(set(f for r in RESTAURANTS for f in r["food_type"])),
        "diets": sorted(set(d for r in RESTAURANTS for d in r["diet"])),
        "vibes": sorted(set(v for r in RESTAURANTS for v in r["vibe"])),
        "use_cases": sorted(set(u for r in RESTAURANTS for u in r["use_case"])),
        "cities": sorted(set(r["city"] for r in RESTAURANTS)),
        "total": len(RESTAURANTS)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
