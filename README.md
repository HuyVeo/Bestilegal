# Chatbot Viva - Vietnamese Real Estate Legal RAG

Chatbot RAG tra cuu luat bat dong san Viet Nam. Ket hop kien thuc noi bo (Qdrant vector DB) va tim kiem web (Tavily), toan bo tuong tac bang tieng Viet.

## Kien truc

```
Frontend (SSE streaming)
        |
   Flask API (Blueprints)
        |
   chat_orchestrator (10-step pipeline)
        |
   +-----------+-----------+-----------+
   |           |           |           |
 RAG Search  Web Search  Stock API  LLM Stream
 (Qdrant +   (Tavily     (CafeF)   (Gemini/
  BM25 +      pipeline)             OpenAI)
  reranker)
        |
   PostgreSQL (conversations) + Redis (cache)
```

### Module structure

```
src/chatbot_viva/
+-- api/                  # Flask app + Blueprint endpoints
|   +-- main.py           # App factory, middleware, startup
|   +-- endpoints/        # chat, conversations, health, legal
+-- services/             # Business logic orchestration
|   +-- chat_orchestrator.py  # 10-step pipeline
|   +-- chat_service.py       # LLM streaming + prompt selection
|   +-- rag_service.py        # Vector + BM25 + reranker + recursive RAG
|   +-- conversation_service.py  # CRUD (PostgreSQL)
|   +-- engine.py              # Chatbot initialization
+-- conversation/         # Query analysis, context, memory
|   +-- query_analyzer.py     # 1 LLM call: classify + rewrite
|   +-- context.py            # Conversation context manager
|   +-- memory.py             # User profile (per-conversation)
|   +-- prompt_templates.py   # Style-based prompt templates
|   +-- suggestions.py        # Follow-up question generator
+-- retrieval/            # Search infrastructure
|   +-- vector_store.py       # Qdrant client (thread-safe)
|   +-- hybrid_search.py      # BM25 + vector scoring
|   +-- reranker.py           # LLM-based re-ranking
|   +-- metadata_filter.py    # Topic/urgency/year filtering
+-- quality/              # Result quality control
|   +-- source_reliability.py # Domain credibility scoring
|   +-- snippet_ranking.py    # Snippet extraction + dedup
+-- tools/                # External integrations
|   +-- legal_web_search.py   # 5-step web pipeline (Tavily)
|   +-- legal_article_crawler.py  # Crawl hethongphapluat.vn
|   +-- stock_price.py        # CafeF realtime stock prices
|   +-- web_search.py         # General web search tool
|   +-- tavily_utils.py       # Unified Tavily client
|   +-- comparable_search.py  # Property price extraction
+-- llm/                  # LLM abstraction
|   +-- factory.py            # Multi-provider (Gemini/OpenAI/Anthropic)
+-- processing/           # Document ingestion
|   +-- loader.py             # DOCX/MD loading + article chunking
|   +-- adapters.py           # Bank rates, land prices, tax calc
|   +-- doc_utils.py          # Document name extraction
+-- core/                 # Cross-cutting concerns
    +-- config.py             # Centralized config (all env vars)
    +-- singleton.py          # Thread-safe @singleton decorator
    +-- patterns.py           # Shared regex patterns
    +-- db.py                 # PostgreSQL connection pool
    +-- cache.py              # Redis/in-memory response cache
    +-- security.py           # Auth, rate limiting, headers
    +-- exceptions.py         # Custom exception hierarchy
    +-- logging_config.py     # Structured logging
    +-- tracing.py            # Langfuse LLM observability
```

## Chat Pipeline

```
POST /api/chat
  1. Query Analysis     -- 1 LLM call: action, style, category, search_query
  2. Non-search         -- greeting/clarify: respond directly
  3. Cache check        -- hit: return cached (with conversation context fingerprint)
  4. Parallel search    -- RAG (Qdrant+BM25+reranker) || Web (Tavily 10 pages)
  5. Build context      -- merge RAG + web + stock prices
  6. LLM streaming      -- SSE chunks, style-based prompt
  7. Post-process       -- citation linking [N] -> [[N]](url)
  8. Cache + save       -- PostgreSQL conversation, Redis response cache
  9. Suggestions        -- LLM-generated follow-up questions
 10. Legal basis        -- enrich refs from hethongphapluat.vn
  -> SSE 'done' event:  final_response, legal_basis, web_results, sources, warnings
```

## Quick Start

### Docker (recommended)

```bash
# Configure
cp .env.example .env
# Edit .env with your API keys

# Start all services
docker compose up -d --build

# Verify
curl http://localhost:5000/api/health
```

### Local Development

```bash
# Install dependencies
uv venv && uv sync && uv pip install -e ".[dev,prod,redis]"

# Start PostgreSQL (required)
docker run -d --name chatbot-pg -p 5433:5432 \
  -e POSTGRES_DB=chatbot_db -e POSTGRES_USER=chatbot -e POSTGRES_PASSWORD=changeme \
  postgres:16-alpine

# Run
python src/chatbot_viva/api/main.py
# -> http://localhost:5000
```

## Configuration (.env)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | No | openai | gemini, openai, anthropic |
| `LLM_MODEL` | No | gpt-4.1-nano | Primary LLM model |
| `OPENAI_API_KEY` | Yes | - | For embeddings (always needed) |
| `GEMINI_API_KEY` | If provider=gemini | - | Google Gemini API key |
| `TAVILY_API_KEY` | Yes | - | Web search |
| `DATABASE_URL` | Yes | - | PostgreSQL connection |
| `QDRANT_URL` | No | local | Qdrant cloud URL |
| `QDRANT_API_KEY` | If cloud | - | Qdrant auth |
| `API_KEY` | No | - | API auth (disabled if empty) |
| `CACHE_ENABLED` | No | true | Redis/in-memory cache |
| `RERANK_ENABLED` | No | true | LLM reranking |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Chat (SSE streaming) |
| GET | `/api/health` | Health check |
| GET | `/api/conversations` | List conversations |
| GET | `/api/conversations/:id` | Get conversation |
| PATCH | `/api/conversations/:id` | Rename conversation |
| DELETE | `/api/conversations/:id` | Delete conversation |
| POST | `/api/legal-article/search` | Search legal articles |
| POST | `/api/legal-article/clean` | Clean article formatting |
| GET | `/api/suggestions/default` | Default suggestions |
| GET | `/api/cache/stats` | Cache statistics |
| POST | `/api/cache/clear` | Clear cache |

## Development

```bash
# Run tests (86 tests)
python -m pytest tests/ -v

# Lint
ruff check src/

# Type check structure
python -c "from chatbot_viva.api.main import app; print('OK')"
```

## Tech Stack

- **LLM**: Google Gemini / OpenAI / Anthropic (via LangChain)
- **Embeddings**: OpenAI text-embedding-3-small
- **Vector DB**: Qdrant (cloud or local)
- **Web Search**: Tavily API
- **Backend**: Flask + SSE + Gunicorn/Gevent
- **Database**: PostgreSQL (psycopg3 + connection pool)
- **Cache**: Redis (fallback: in-memory LRU)
- **Observability**: Langfuse
- **Frontend**: Single-page HTML + vanilla JS
