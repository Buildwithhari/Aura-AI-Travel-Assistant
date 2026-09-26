# Aura · AI Travel Assistant (prototype)

A conversational travel assistant built with **Python / Flask**. Users describe trips in their own
words (English, Kannada, Hindi, or mixed/Hinglish) and Aura searches **sample** flights and hotels,
builds trip plans from **curated sample itineraries**, and walks through a **demo checkout**.

> **Nothing here is live.** Flights, fares, hotels, availability, seat maps, the checkout and the
> flight-delay alert are all sample/simulated data. No payment is taken, no reservation is made and no
> PNR is issued. The UI labels every such card "Sample data" / "Demo" / "Simulated update".

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                                           # http://localhost:5000   (admin: /admin)
```

No API key, model download or internet connection is needed: the default `LLM_PROVIDER=custom`
runs entirely on rules + a scikit-learn classifier. Copy `.env.example` to `.env` to change settings.

### Tests
```bash
python run_tests.py          # no extra dependencies (94 tests)
pip install -r requirements-dev.txt && pytest -q     # same tests via pytest
python tests/ui_smoke.py http://localhost:5000       # optional browser check (needs playwright)
```

---

## How a message flows (read this to explain the code)

```
browser (static/script.js)
   │  POST /chat {message | action+payload, reply_language, language_mode, tz}
   ▼
app.py ── strips technical fields from the response, logs them to SQLite (analytics_store.py)
   ▼
orchestrator.run_turn(state, text, …)          ← custom state machine (not LangGraph)
   1. language   : reply language = manual choice, or auto-detected from script (i18n.py)
   2. understand : nlu_rules.py (deterministic: places, dates, passengers, cabin, trip type,
                   interests, budget, commands)  → intent_classifier.py (TF-IDF + SVM)
                   → optional mBERT → optional LLM *only if nothing else found a signal*
   3. pending    : is the user answering an open question (which airport? departure or return?)
                   — or doing something else? Other intents win; the question is re-asked after.
   4. route      : flight / hotel / plan / knowledge (rag_engine.py) / social
   5. validate   : dates (past, impossible, too far, return > departure, leg order), same airport,
                   passenger limits, stay length
   6. act        : providers.py searches sample data; price_summary() computes every total
   7. finalize   : "Got it: …" acknowledgement of what changed THIS turn + next question,
                   cards ("blocks"), quick replies, date-picker hint
   ▼
optional LLM rewording (llm.rephrase) — accepted only if every number/date/price/code survives
```

**State is structured, not a flat slot bag.** `state["flight"]` holds `trip_type`, a list of `legs`
(origin/destination/date each), `return_date`, passengers and cabin. One-way, round-trip and
multi-city are therefore separate shapes of the same structure, and a correction like
"change flight 2 to the 15th" edits exactly one field. `compat_slots()` still exposes the old flat
view for the legacy tests.

**The LLM never owns facts.** `llm.extract()` output is re-validated through the same location and
date resolvers as typed text (unknown places and out-of-range counts are dropped), and
`llm.rephrase()` / `llm.translate()` are rejected if they change or drop any number, date, price,
airport code or flight number. Every LLM function returns `None` on any failure, so the
deterministic path always answers.

## File map

| File | Role |
|---|---|
| `app.py` | Flask routes; response sanitising (`_public`); JSON error envelopes |
| `orchestrator.py` | Conversation state machine, validation, flight/hotel/plan/review/checkout/alert/seat steps |
| `nlu_rules.py` | Rule-based multilingual extraction (roles via *from/to*, *se/tak*, *-ಇಂದ/-ಗೆ*) |
| `locations.py` | Checked catalogue: airports (IATA, city, state/country, coordinates), all 28 states + 8 UTs, aliases in 3 scripts, typo suggestions |
| `dates.py` | Time-zone-aware date parsing (relative, day-first numeric, ranges, Kannada/Hindi words and digits) |
| `providers.py` | Sample flight/hotel/itinerary providers + `price_summary()` (single source of truth for totals) |
| `i18n.py` | All customer-facing text in en/kn/hi (conversation + UI labels) |
| `intent_classifier.py` | Original TF-IDF classifier (city tables now derived from `locations.py`) |
| `rag_engine.py` + `data/travel_knowledge.json` | Retrieval over the travel-policy knowledge base |
| `llm/` | Optional Ollama / OpenRouter / Groq provider + guarded extract / rephrase / translate |
| `nlu/mbert_classifier.py` | Optional multilingual BERT intent model |
| `analytics_store.py`, `templates/admin.html` | SQLite interaction log + admin dashboard (intent, confidence, source live here) |
| `data/hotels.json` | 11 cities × 5–6 fictional hotels (real neighbourhoods) |
| `data/itineraries.json` | 4 curated plans: Kerala, Rajasthan (domestic); Dubai, Singapore (international) |
| `tools/make_hotel_images.py` | Regenerates the local destination-themed hotel images + `fallback.svg` |
| `templates/index.html`, `static/script.js`, `static/style.css` | Customer UI |
| `templates/seat_selection.html` | Sample seat map (demo) |

## What is simulated vs what needs credentials

| Capability | Status |
|---|---|
| Flights, fares, schedules, connections | **Sample** — deterministic per route/date/cabin (same query → same results) |
| Hotels, prices, ratings, images | **Sample** — fictional properties, local images with fallback |
| Itineraries | **Curated samples**, adjusted by interests/budget/days; marked "Adjusted sample". Unsupported destinations are refused, not invented |
| Seat map | **Sample**; seats are validated and added to the summary. Nothing is reserved |
| Checkout | **Demo** — no payment form, no card, no reservation, no PNR |
| Flight update | **Simulated** 30-minute delay, shown in-app only. No airline feed, no push notifications |
| Travel-rule answers (baggage, visa, check-in…) | Local knowledge base with built-in English, Kannada and Hindi answers (no LLM needed) |
| Understanding unusual phrasing | Rules + classifier work offline; **LLM (`LLM_API_KEY` or Ollama)** improves coverage |
| Natural rewording of replies | **Needs an LLM**; otherwise reviewed templates are used |
| mBERT intent model | Optional (`USE_MBERT=true`, needs transformers + torch) |
| Voice input / read-aloud | Browser Web Speech API (Chrome/Edge best). Kannada recognition depends on the browser |

To go live you would replace the three `Sample*Provider` classes in `providers.py` with real
GDS/OTA/hotel APIs behind the same method signatures, and add a real payment/booking step.

## Languages

- **Reply language** (sidebar): Auto, English, ಕನ್ನಡ, हिन्दी. In *Auto*, Aura follows what you type:
  Kannada or Devanagari script, **or Kannada/Hindi written in English letters** ("naale bengaluru inda
  delhi ge flight beku", "mujhe kal delhi jana hai"). A full English sentence switches back to English.
  Choosing a language (or typing "reply in Kannada") pins it for the whole journey, including
  card labels, dates and the seat page.
- **Speech-recognition language** (mic selector) is separate: you can speak Hindi and read Kannada.
  The transcript is placed in the input box for you to check and edit — it is never sent automatically.
- City names and codes are kept in Latin script in replies (e.g. "Bengaluru (BLR)") so they stay exact.

## Configuration (`.env`)

See `.env.example`. Notable: `LLM_PROVIDER` (`custom` | `ollama` | `api`), `LLM_API_KEY`,
`LLM_REPHRASE`, `USE_MBERT`, `PORT`, `EXPOSE_DEBUG` (developer only — adds intent/confidence to
`/chat` responses; they're always in the server log and `/admin`).

## Known limitations

- Sessions are in memory (one process). Use Redis or similar for multiple workers.
- Location catalogue covers major airports (117), not every airstrip; unknown places get a
  "did you mean" or a clear "not found".
- Romanized Kannada/Hindi is detected from common words (beku, naale, chahiye…); very short messages may stay in the current language.
- Kannada/Hindi understanding is rule-based for travel phrases; long free-form Kannada works best with an LLM configured.
- Hotel data exists for 11 cities; other cities are declined with the list of supported ones.

## Changes in this upgrade (summary)

Rewritten: orchestrator (structured multi-leg state, corrections, pending clarifications),
providers, UI, seat page, `app.py`. New: `locations.py`, `dates.py`, `nlu_rules.py`, `i18n.py`,
hotel/itinerary data, generated images, test suites. Fixed: wrong IATA codes (Ranchi IXR, Udaipur
UDR), empty summaries, assumed round trips, international searches returning nothing, fake
"Seats confirmed!" alert, feedback prompt after every message, technical badges in the customer UI.
Removed: `static/ai_debug.js` (debug overlay that wrapped `fetch`), unused `localizer.py`, and the
outdated `UPGRADE_NOTES.md` / `ADVANCED_UPGRADE_GUIDE.md`.
