# Product Requirements Document

## Product Overview

- **Domain**: A forum for writers to share and discuss their current projects and ideas
- **Value Proposition**: Help writers share and get their projects seen easily
- **Type**: Web application
- **Category**: Forum / Content & Community platform

## Vision & Problem Statement

Writers often lack a way to get their work seen or receive meaningful
feedback. Existing options — social media feeds and in-person sharing —
either bury creative writing under unrelated content or limit reach to
the writer's immediate circle. This product provides a dedicated space
where writers can post their work-in-progress and ideas, and have them
surfaced to readers who actually care about the kind of writing they do.

## Target Audience

- **Primary**: Passionate creatives — independent writers seeking community and visibility
- **User Description**: A young, passionate writer who wants to discuss and share their work with likeminded individuals
- **Key Pain Point**: Lack of likeminded people to share work with and receive feedback from
- **Secondary Users**: None — moderation is performed by an automated AI system rather than human moderators

### Current Solutions

Today, writers cobble together visibility using social media platforms
(Twitter/X, Instagram, TikTok) and in-person channels (writing groups,
workshops, friends and family). Social media buries creative writing
under algorithmic noise that favors short, broad-appeal content; in-person
sharing is constrained to the writer's existing circle. Neither
consistently connects a writer with readers who share their interests.

## Features

### MVP (Must Have)

- **User authentication** — account creation and sign-in
- **User profiles** — public profile per user with their posts and bio
- **Post creation** — writers create text posts to share work and ideas
- **Personalized home page** — recommends recently submitted posts based on a taste questionnaire filled out at account creation
- **AI-based moderation** — automated classifiers screen every post for NSFW, hateful, and AI-generated content; flagged posts are blocked or removed without human moderator involvement

### Out of Scope (v1)

- Media uploads (images, attachments)
- Real-time chat / direct messaging
- Video content

### Core Value Proposition

Get a writer's work seen by people with similar interests. Everything
else in the product serves this single outcome.

## Success Metrics

- **Primary Metric**: Daily / Monthly Active Users
- **Secondary Quality Bar**: High-quality automated moderation — AI classifiers reliably keep NSFW, hateful, and AI-generated content out of the feed with low false-positive rates on legitimate writing
- **3-Month Target**: 250 registered users

## Competitive Analysis

- **Competitors / Alternatives**: Reddit, Wattpad
- **Differentiator**: A smaller, more enjoyable community atmosphere — curated by interest-based recommendations and consistent AI moderation, rather than scale-driven engagement metrics

## Constraints & Requirements

- **Timeline**: 2-3 months to launch
- **Key Constraint**: AI moderation accuracy — the system depends entirely on automated classifiers correctly detecting AI-generated, NSFW, and hateful content with acceptable false-positive and false-negative rates; there are no human moderators to catch misses or appeal incorrect removals
- **Technical Stack**:
  - Google Cloud Platform (Cloud Run)
  - Neon (serverless Postgres with per-PR branching)
  - FastAPI (Python 3.12) + Jinja2 + HTMX
  - SQLModel + Alembic for the database layer

## Open Questions

- How will the taste questionnaire be structured (genres, tones, lengths, themes)?
- What is the recommendation algorithm baseline for v1 — simple tag-overlap, embeddings-based similarity, or something else?
- Which AI classifiers / providers will be used for NSFW, hateful, and AI-generated content detection, given known reliability limits of AI-text detectors?
- How are false positives handled when the AI incorrectly flags legitimate writing — automatic appeal queue, user-visible reason, retry against a second model?
- What is the moderation policy when classifier confidence is low (block, allow, soft-flag)?
- Are there legal or ToS implications of fully automated content removal with no human review path?
