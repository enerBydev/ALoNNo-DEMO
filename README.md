# ALoNNo — matching demo

**Live: https://alonno-demo.enerby212.workers.dev**

Type one sentence — in German or in English — and the system works out what you meant, finds
people and plans that fit, ranks them with a real percentage, and explains each one.

Built in seven days as a free demo for the ALoNNo project. **Synthetic data only. No real people.**

---

## What to try first

The ten sentences on the page are **your own**, verbatim. Click any of them. Two are worth
watching closely:

- **Sentence 1** (German, *"Ich habe noch ein Ticket für Burna Boy…"*) — the top result is a
  profile written **in English**. A German query found an English profile: that is the
  cross-language matching, and no filter-based product can do it.
- **Sentence 6** (English, *"I want to go to a Coldplay concert… I do not have a ticket yet"*) —
  the top result is the person who **has a spare ticket**, and their plan is written in German.
  This is the mirror of sentence 1, and it is the connection a search box cannot make.

Open **"Where does the number come from?"** on any result. The seven components and their points
are there, and they add up to the percentage shown. You can check the arithmetic by hand.

## How the matching works — five layers, cheapest first

| | | Cost |
|---|---|---|
| **0 · Understanding** | One small-model call turns the sentence into a structured object: archetype, city, date, subject, what must match | ~1 call per search |
| **1 · Hard filters** | Date, radius (PostGIS `ST_DWithin`), category, seats, language. Turns thousands of rows into hundreds | an index scan |
| **2 · Retrieval** | HNSW vector search **and** full-text search over the same filtered set, fused with Reciprocal Rank Fusion | an index lookup |
| **3 · Scoring** | Weighted arithmetic over named components. **This is where the percentage comes from** | zero |
| **4 · Explanation** | One sentence per shown result, generated from the components that already exist | bounded by results shown, not candidates evaluated |

**Embeddings are computed when content is written, never when it is searched.** That is the
property that keeps the AI bill flat as searches grow.

**The model writes the sentence. The model never writes the number.** The percentage is
arithmetic — testable, tunable, and the same every time.

## What is demo and what is reusable

| Reusable — this is the architecture | Demo-only — throwaway |
|---|---|
| The five-layer design and the order of the layers | This repository's code: no auth, no RLS policies, no migrations |
| The database schema: profiles, plans, **intents**, with pgvector + PostGIS | The synthetic seed and its ten planted scenarios |
| The scoring model and its seven components | The hardcoded city coordinates |
| The hybrid retrieval (vector + keyword, fused by RRF) | The single-page UI |
| The decision to compute embeddings on write | The provider choice, which was made on what was available this week |
| The archetype decision tree, applied in code rather than by the model | |

## Honest limits

- **Sentence 2 is hybrid** — it should return both people and plans, and today it resolves as
  plan-to-plan. It is the one case of the ten that is not right yet.
- **A cold search takes 13-45 seconds**, because the model provider's latency varies that much.
  Repeated searches are cached and answer in ~0.3 s, and the ten example sentences are pre-warmed.
  If the parser takes more than 12 seconds, a rule-based fallback answers instead — and the
  response says so rather than hiding it.
- **The daily AI budget is capped.** Past it, the cached examples still work and fresh searches
  wait for the next day. It is a public URL with a real API key behind it.
- The data is synthetic and was designed so the ranking has something to prove: each scenario has
  one perfect match, a few good ones, and four near-misses that each fail for exactly one reason.

## Running it

```bash
just ci          # the whole gate: install, catalog, tests, audit, secrets, surface, facts
just seed        # generate db/seed.json — deterministic, no network
just sembrar     # load it into Postgres with embeddings
just reanclar    # shift every date, keeping their relative distances
just frases      # the ten sentences against the deployed demo; also warms the cache
```

Nuxt 4 + Nitro on Cloudflare Workers · PostgreSQL with pgvector and PostGIS on Supabase, **EU
region (Frankfurt)** · NVIDIA NIM for embeddings and text.

---

enerBydev · Rene Mendoza
