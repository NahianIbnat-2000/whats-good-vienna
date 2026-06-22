# 🍽️ What's Good Vienna? — AI Restaurant Finder

> **Search restaurants by mood, taste, and use case — not just cuisine.**

An AI-powered chatbot that helps you find the perfect restaurant in Vienna. Instead of searching by cuisine alone, you can ask for "spicy Indian curry under €15 for a quick lunch" or "a quiet cafe with wifi and sweet desserts for studying."

![What's Good Vienna?](screenshot.png)

---

## ✨ Features

- **Natural language queries** — "spicy halal food near me under €15"
- **Mood & taste search** — spicy, mild, sweet, sour, umami, creamy, fried, soup, curry
- **Use case matching** — date, study cafe, quick lunch, family, cheap eats, takeaway, late-night
- **Dietary filters** — halal, vegetarian, vegan
- **Live map** — OpenStreetMap with restaurant markers
- **AI explanations** — why each restaurant matches your query
- **68 real Vienna restaurants** across 20 cuisines

---

## 🚀 Quick Start

### Option 1: Static Frontend (GitHub Pages)

Just open `index.html` in a browser. It works entirely client-side with embedded data.

```bash
git clone https://github.com/YOUR_USERNAME/whats-good-vienna.git
cd whats-good-vienna
# Open index.html in your browser
```

### Option 2: Full Stack (FastAPI + React)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the backend
python main.py
# API available at http://localhost:8000

# 3. Open index.html in browser (or serve with any static server)
python -m http.server 3000
# Frontend at http://localhost:3000
```

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/chat` | POST | Natural language restaurant search |
| `/restaurants` | GET | Filtered restaurant list |
| `/metadata` | GET | All available categories |

### Example: Chat API

```bash
curl -X POST http://localhost:8000/chat   -H "Content-Type: application/json"   -d '{"query": "spicy Indian curry under €15", "user_lat": 48.2082, "user_lon": 16.3738}'
```

---

## 🗂️ Data Schema

Each restaurant has these fields:

| Field | Example | Description |
|-------|---------|-------------|
| `name` | "Saffron" | Restaurant name |
| `cuisine` | "Indian" | Cuisine type |
| `city` | "Vienna" | City |
| `lat` / `lon` | 48.1967, 16.3630 | Coordinates |
| `price_level` | "€€" | Price (€ / €€ / €€€) |
| `rating` | 4.4 | Star rating |
| `taste_tags` | ["spicy", "curry", "mild"] | Taste profile |
| `food_type` | ["rice", "naan", "curry"] | Food categories |
| `diet` | ["halal", "vegetarian"] | Dietary options |
| `vibe` | ["casual", "family"] | Atmosphere |
| `use_case` | ["family", "quick lunch"] | Best use cases |
| `opening_hours` | "Mo-Su 12:00-23:00" | Hours |
| `source` | "OSM" | Data source |

---

## 🧠 Query Examples

| Query | What It Finds |
|-------|---------------|
| "spicy Indian curry under €15" | Saffron, Tandoor, Bombay Palace |
| "Vietnamese pho for quick lunch" | Vietnam Village, Pho 24, Banh Mi Corner |
| "Chinese hot pot for family" | Hot Pot Vienna, Sichuan Kitchen |
| "quiet study cafe with wifi and sweet desserts" | Café Phil, Café Kafka, Kipferl |
| "halal kebab takeaway open late" | Kebap House, Sultan |
| "romantic Italian date night under €25" | Trattoria da Enzo, La Piazza |
| "vegan burger cheap eats" | Swing Kitchen |
| "Korean BBQ for group dinner" | Kim Kocht, K-BBQ, Seoul Kitchen |
| "Japanese ramen with spicy broth" | Ramen Bar, Sakura |
| "Austrian schnitzel for family lunch" | Figlmüller, Plachutta, Gasthaus Pöschl |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Leaflet (OpenStreetMap) |
| Backend | FastAPI + Python |
| Data | JSON (expandable to PostgreSQL + PostGIS) |
| Map | OpenStreetMap tiles |

---

## 🗺️ Future Roadmap

- [ ] Live OSM Overpass API integration
- [ ] Google Places API enrichment (photos, real reviews, live hours)
- [ ] PostgreSQL + PostGIS database
- [ ] OpenAI API for true NLU query understanding
- [ ] Expand to Graz, Linz, Salzburg, Innsbruck
- [ ] User favorites & history
- [ ] Mobile app (React Native)

---

## 📄 License

MIT License — free to use, modify, and deploy.

---

Made with ❤️ in Vienna 🇦🇹

**What's Good Vienna?** — Because you deserve better than random Google results.
