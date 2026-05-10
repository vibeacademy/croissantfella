# Technical Architecture

## Overview

A server-rendered web forum where writers share text posts and a
personalized home page surfaces recently submitted posts to readers
with overlapping interests. Authentication is passwordless (magic
link). Every post passes through an automated moderation pipeline
before becoming publicly visible. The system is a single FastAPI
application deployed to Cloud Run, backed by Neon Postgres.

The architecture is deliberately a **monolith** — the team is one
person, the domain is small, and the scale target is 250 registered
users in three months. Service boundaries can be introduced later if
load patterns demand it; introducing them now would only add latency
and operational cost.

## Technology Stack

### Frontend
- **Templates**: Jinja2 (server-rendered, no client build step)
- **Interactivity**: HTMX 2.x for fragment swaps, form posts, and progressive enhancement
- **Styling**: Pico.css via CDN (class-less; replace if it becomes a constraint)
- **No JS framework, no bundler.** Reflects the "small team, fast launch" constraint and the read-heavy nature of a forum.

### Backend
- **Runtime**: Python 3.12
- **Framework**: FastAPI + Uvicorn
- **Database layer**: SQLModel + Alembic
- **Auth**: Custom magic-link flow (signed single-use tokens) + Starlette `SessionMiddleware` for session cookies
- **Email**: Resend transactional email API (third-party — GCP has no native equivalent)
- **AI moderation**: OpenAI Moderation API (`omni-moderation-latest`)
- **HTTP client (outbound)**: `httpx` (async)
- **Package manager**: uv
- **Lint / format / type check**: ruff + mypy
- **Tests**: pytest + httpx + in-memory SQLite fixture

### Database
- **Primary**: Neon Postgres (per-PR branching for ephemeral preview environments)
- **Cache**: None in v1. Re-evaluate if recommendation queries become hot.
- **Search**: None in v1. Postgres full-text search if needed later.

### Infrastructure
- **Hosting**: GCP Cloud Run (scale-to-zero, single service)
- **Container registry**: Artifact Registry
- **Secrets**: Google Secret Manager (OpenAI API key, Resend API key, session secret)
- **CI/CD**: GitHub Actions (existing `.github/workflows/`)
- **Observability**: Google Cloud Logging + Error Reporting (zero-setup default for Cloud Run; FastAPI exceptions auto-group). Sentry optional later.

## System Design

### Component Diagram

```
        ┌────────────────────────────────────────────┐
        │              Browser (HTMX)                │
        └───────────────────┬────────────────────────┘
                            │ HTTP (HTML fragments + full pages)
                            ▼
        ┌────────────────────────────────────────────┐
        │   Cloud Run service: FastAPI (single app)  │
        │  ┌──────────────────────────────────────┐  │
        │  │ Routes                               │  │
        │  │  /auth/*   — magic link send/verify  │  │
        │  │  /         — home (recommended feed) │  │
        │  │  /posts/*  — create / view post      │  │
        │  │  /u/{user} — public profile          │  │
        │  │  /onboard  — taste questionnaire     │  │
        │  │  /healthz  — Cloud Run health probe  │  │
        │  └────────────┬───────────────┬─────────┘  │
        │               │               │            │
        │   ┌───────────▼──┐  ┌─────────▼─────────┐  │
        │   │ Auth service │  │ Moderation pipe.  │  │
        │   │ (magic link) │  │ (OpenAI Moder.)   │  │
        │   └──────┬───────┘  └──────────┬────────┘  │
        │          │                     │           │
        │   ┌──────▼─────────────────────▼────────┐  │
        │   │ Persistence (SQLModel sessions)     │  │
        │   └───────────────────┬─────────────────┘  │
        └───────────────────────┼────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Neon Postgres (pooled)│
                    └───────────────────────┘

        Outbound integrations (sync, server-side):
          - Resend API   (send magic link emails)
          - OpenAI API   (post moderation classification)
```

### Data Flow

**Sign-up / sign-in** (magic link):
1. User enters email on `/auth/login`
2. Backend creates `MagicLinkToken` row (random 32-byte token, hashed at rest, 15-minute expiry, single-use)
3. Backend calls Resend API to send email containing `/auth/verify?token=<raw>`
4. User clicks link → backend hashes token, looks up row, verifies expiry, deletes row, sets session cookie
5. If first sign-in for this email, create `User` row and redirect to `/onboard` for taste questionnaire
6. Otherwise redirect to `/`

**Post / comment creation** (same pipeline, parameterized by subject type):
1. User submits content (markdown body + tag selections for posts; plain markdown for comments) on `/posts/new` or `/posts/{id}/comments`
2. Backend creates the row with `status = 'pending_moderation'`
3. Backend synchronously calls OpenAI Moderation API with the body text
4. Backend writes `ModerationResult` row (`subject_type` = `'post'` or `'comment'`, full response stored as JSONB for audit)
5. Decision logic:
   - Any `flagged` category with score ≥ 0.85 → `status = 'blocked'`, user shown rejection reason
   - Otherwise → `status = 'published'`, content becomes visible
6. Synchronous moderation is acceptable at MVP scale (~250 users, low post + comment rate). Move to async (Cloud Tasks) if p95 submit latency exceeds 1.5s.
7. Comments support **one level of nesting** (`parent_id` may reference another comment but a comment with a `parent_id` may not itself be replied to). This keeps the discussion structure simple and the rendering predictable.

**Home feed (recommendations)**:
1. User loads `/`
2. Query: published posts from last N days (default N=14), score by tag overlap with user's taste profile, sort by `score * recency_decay`, take top 50
3. Tag overlap = Jaccard similarity over (genres ∪ tones ∪ form_lengths) using Postgres array operators (`&&`, `array_length(... && ...)`) on GIN-indexed `text[]` columns
4. Cold start (no taste profile yet) → redirect to `/onboard`
5. Cold start (no posts match) → fall back to "recent across the site" feed

### API Design

Server-rendered HTML routes (HTMX-driven). No REST/JSON API in v1. HTMX
endpoints return either full pages or HTML fragments depending on whether
the request includes the `HX-Request` header.

Convention: HTMX fragment routes return raw partials (no `<html>`/`<head>`)
and live under the same path as their full-page equivalent — the handler
branches on `HX-Request`. Tests assert `"<html" not in response.text` for
fragment endpoints.

## Data Models

### Core Entities

| Entity | Purpose | Lifecycle |
|---|---|---|
| `User` | Account + profile | Created on first verified magic link |
| `TasteProfile` | Questionnaire answers used for recommendations | Created on `/onboard` completion; editable later |
| `Post` | Text post by a user | Created → moderated → published or blocked |
| `Comment` | Reply on a post (threaded one level deep) | Created → moderated → published or blocked |
| `ModerationResult` | Audit record of every moderation call (post or comment) | Append-only; never deleted |
| `MagicLinkToken` | Single-use sign-in token | Created on `/auth/login`; deleted after verification or expiry |
| `Session` | Server session cookie state | Managed by Starlette `SessionMiddleware` (signed cookie, no DB row) |

### Database Schema

```
users
  id              uuid pk
  email           text unique not null
  display_name    text not null
  bio             text
  created_at      timestamptz default now()
  last_seen_at    timestamptz

taste_profiles
  user_id         uuid pk references users(id) on delete cascade
  genres          text[] not null    -- GIN index
  tones           text[] not null    -- GIN index
  form_lengths    text[] not null    -- GIN index
  updated_at      timestamptz default now()

posts
  id              uuid pk
  author_id       uuid not null references users(id) on delete cascade
  title           text not null
  body            text not null
  genres          text[] not null    -- GIN index
  tones           text[] not null    -- GIN index
  form_length     text not null
  status          text not null      -- 'pending_moderation' | 'published' | 'blocked'
  created_at      timestamptz default now()
  published_at    timestamptz
  index on (status, published_at desc)  -- feed query

comments
  id              uuid pk
  post_id         uuid not null references posts(id) on delete cascade
  author_id       uuid not null references users(id) on delete cascade
  parent_id       uuid references comments(id) on delete cascade  -- one level of nesting
  body            text not null
  status          text not null      -- 'pending_moderation' | 'published' | 'blocked'
  created_at      timestamptz default now()
  published_at    timestamptz
  index on (post_id, status, created_at)

moderation_results
  id              uuid pk
  subject_type    text not null      -- 'post' | 'comment'
  subject_id      uuid not null      -- FK enforced at app layer (polymorphic)
  provider        text not null      -- 'openai-moderation' for v1
  raw_response    jsonb not null
  flagged         bool not null
  categories      text[] not null
  max_score       numeric not null
  decided_at      timestamptz default now()
  index on (subject_type, subject_id)

magic_link_tokens
  id              uuid pk
  email           text not null
  token_hash      bytea not null     -- sha256 of raw token; raw never stored
  expires_at      timestamptz not null
  consumed_at     timestamptz
  created_at      timestamptz default now()
  index on (token_hash) where consumed_at is null
```

**Tag taxonomy** is a fixed Python enum (not a DB table) for v1. Validation
happens at the application layer. If the taxonomy needs to evolve
frequently, promote it to a DB table later.

### Vocabulary (v1)

- **Genres**: `literary`, `sci_fi`, `fantasy`, `horror`, `romance`, `mystery`, `poetry`, `essay`, `memoir`, `screenplay`, `fanfic`, `other`
- **Tones**: `dark`, `comedic`, `contemplative`, `action`, `romantic`, `experimental`
- **Form lengths**: `flash`, `short_story`, `novella_chapter`, `novel_chapter`, `serial`, `poem`

## Development Standards

### Code Style
- **Formatter**: `ruff format` (replaces Black)
- **Linter**: `ruff check` with the default rule set + `I` (imports) + `N` (naming) + `B` (bugbear) + `UP` (pyupgrade)
- **Type checker**: `mypy` in strict mode for `app/`
- **Naming**: snake_case for functions and modules; PascalCase for SQLModel and Pydantic classes
- **Imports**: stdlib → third-party → first-party blocks (ruff handles this)

### Testing Requirements
- **Unit tests**: cover pure logic (recommendation scoring, moderation decision policy, token hashing)
- **Integration tests**: HTTP-level via `TestClient` with overridden `get_session` (in-memory SQLite). Every public route has at least one happy-path and one auth/error path test.
- **Coverage target**: 80% for `app/`, enforced by `pytest --cov` in CI
- **HTMX fragment tests**: assert `"<html" not in response.text` to catch accidental full-page returns
- **External API tests**: Resend and OpenAI calls are mocked in unit/integration tests. One opt-in smoke test per provider hits the real API behind a `--external` pytest flag.

### Documentation
- Architecture decisions in this document under "Architecture Decision Records"
- Per-module docstrings only when behavior is non-obvious
- No per-function docstrings unless the WHY is non-obvious (matches existing CLAUDE.md guidance)

### Code Review
- All changes via PR
- Pre-push hook (`scripts/hooks`) must pass — never `--no-verify`
- PR Reviewer agent runs first; human merges
- Definition of Done: AC met, code reviewed, tests passing, no lint errors, PR merged

## Security

### Authentication
- **Magic link, single-use, 15-minute expiry**
- Raw token never stored — only `sha256(token)` in DB
- Email enumeration is mitigated by **always returning the same response** from `/auth/login` regardless of whether the email exists
- Rate limit: max 5 magic link requests per email per hour, max 20 per IP per hour (in-process counter is acceptable at MVP scale; move to Redis if multi-instance)
- Session cookie: `HttpOnly`, `Secure`, `SameSite=Lax`, signed with `SESSION_SECRET` from Secret Manager

### Authorization
- Two roles only: anonymous and authenticated
- Authors can edit/delete their own posts; nobody can edit anyone else's
- No admin role in v1 (consistent with PRD: no human moderators)

### Data Protection
- All traffic over HTTPS (Cloud Run-terminated)
- PII in DB: email, display name, bio. No payment info, no addresses.
- Secrets via Secret Manager — no secrets in env vars committed to the repo
- Magic link emails contain a tokenized URL only; no PII in subject lines
- CSRF: HTMX requests include `Hx-Request` header; we additionally enforce a per-session CSRF token on POST/PUT/DELETE forms

### Abuse / safety
- **Moderation is the security boundary for content.** Every post **and every comment** must pass `moderation_results.flagged = false` (or be below the configured score threshold) before `status` transitions to `published`.
- **Fail-closed on moderation outage**: if the OpenAI API is unavailable, posts stay `pending_moderation` and are NOT shown publicly. A retry job processes the queue when the provider recovers. This matches the PRD constraint that there are no human moderators.

## Scalability

### Current Targets
- 250 registered users at month 3
- Low single-digit posts/minute peak
- Read-heavy: home feed and post detail dominate

### Scaling Strategy
- **Cloud Run** auto-scales 0 → N based on concurrency. Configured at `min-instances=0`, `max-instances=10`, `memory=512Mi`, `cpu=1` (existing template defaults).
- **Neon pooled connection** (`-pooler` host) handles connection multiplexing across Cloud Run instances. Pool size on the app side stays small (default 5).
- **Recommendation query**: tag-overlap on GIN-indexed `text[]` columns is fast at this scale. If feed latency p95 > 200ms, add a denormalized `feed_candidates` table refreshed on post publish.
- **Moderation cost**: OpenAI Moderation is free (no per-call charge); rate limits are well above projected throughput.
- **Email cost**: Resend free tier allows 3k emails/month, well above projected magic-link volume.

## Architecture Decision Records

### ADR-001: Monolith over microservices
- **Status**: Accepted
- **Context**: One-person team, 2-3 month timeline, 250-user target.
- **Decision**: Single FastAPI service. No internal service split.
- **Consequences**: Faster delivery, simpler ops. If a future feature needs independent scaling (e.g., moderation as a queue worker), extract it then.

### ADR-002: Magic link over OAuth
- **Status**: Accepted (chosen by founder)
- **Context**: Two viable options were OAuth (Google + GitHub) and magic link.
- **Decision**: Magic link via Resend.
- **Consequences**: No password to store; no third-party identity dependency for users without Google/GitHub accounts. Adds Resend as a runtime dependency. First-time login latency is bounded by email delivery (typically <10s with Resend).

### ADR-003: Tag overlap (not embeddings) for v1 recommendations
- **Status**: Accepted
- **Context**: 250-user scale; "smaller, more enjoyable community" differentiator does not require ML-grade discovery.
- **Decision**: Jaccard overlap of fixed-taxonomy tags between user taste profile and post tags, with recency decay.
- **Consequences**: Explainable, debuggable, no extra infra (no pgvector, no model hosting). Likely to feel mechanical at scale; revisit at 1k+ users.

### ADR-004: OpenAI Moderation for NSFW + hate; defer hard AI-detection
- **Status**: Accepted
- **Context**: PRD requires automated moderation including AI-generated content detection. AI-text classifiers are unreliable.
- **Decision**: Use OpenAI Moderation API for NSFW and hateful content with auto-block on high confidence. **Do not** ship an AI-generated-content classifier in v1; rely on ToS + community reporting (Phase 2 surface) instead.
- **Consequences**: Honest about classifier limits. The PRD constraint about AI-generated content remains an open product decision rather than a false technical solution. Reporting UI is added in Phase 2.

### ADR-005: Synchronous moderation in the request path
- **Status**: Accepted (with revisit trigger)
- **Context**: Posts must not be publicly visible before moderation completes.
- **Decision**: Call OpenAI Moderation inline during `POST /posts/new`. The user waits for the moderation result before seeing their post live.
- **Consequences**: Simpler code; no queue, no worker. Trade-off: post-submit latency includes the OpenAI round-trip (~300-800ms). Move to Cloud Tasks if p95 exceeds 1.5s.

### ADR-006: Server-rendered HTML + HTMX (no SPA)
- **Status**: Accepted (template default; reaffirmed for this product)
- **Context**: Read-heavy forum, simple interactions, no offline requirements.
- **Decision**: Jinja2 + HTMX for all UI.
- **Consequences**: No build step, fast time-to-first-byte, easy SEO. Trade-off: complex client interactions (e.g., rich text editors) need careful integration.

## Open Questions

These remain unresolved and should be addressed during implementation:

- **Markdown rendering**: server-side render with `markdown-it-py` or render in-browser? Server-side is preferred for SEO; revisit if XSS hardening is non-trivial.
- **Email delivery domain**: Resend requires a verified sending domain. What domain will the product use, and who owns DNS?
- **Onboarding skip**: should users be allowed to use the site without completing the taste questionnaire? Currently the design forces it; consider a "skip for now" with a degraded-recommendations experience.
- **Reporting flow** (Phase 2 candidate): if AI-detection isn't shipped in v1, is community reporting in v1 or v2?
- **Comment edit / delete policy**: can authors edit comments after posting? If yes, does an edit re-trigger moderation?
