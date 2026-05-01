# Product Roadmap

## Overview

A 2-3 month path to MVP launch, focused on delivering one outcome:
getting a writer's work in front of readers with similar interests.
Phase 1 ships the minimum surface needed to register, post, and get
recommended; Phase 2 iterates based on real user feedback once a small
community is active.

## Phase 1: MVP

- **Target**: 2-3 months from start
- **Goal**: Deliver the core value proposition — get writers' work seen by people with similar interests
- **Launch Definition**: Public availability with the feature set below and active moderation in place

### Features

| Feature                                  | Priority | Status  |
| ---------------------------------------- | -------- | ------- |
| User authentication                      | P0       | Backlog |
| User profiles                            | P0       | Backlog |
| Post creation                            | P0       | Backlog |
| Taste questionnaire (account onboarding) | P0       | Backlog |
| Personalized home feed (recommendations) | P0       | Backlog |
| Moderation tooling                       | P0       | Backlog |

### Success Criteria

- [ ] 250 registered users within 3 months of launch
- [ ] Active daily/monthly user tracking in place
- [ ] Moderation queue keeps NSFW, hateful, and AI-generated content out of the public feed

### Explicitly Out of Scope

- Media uploads (images, attachments)
- Real-time chat / direct messaging
- Video content

## Phase 2: Iteration

- **Target**: Post-MVP, driven by user feedback
- **Goal**: Deepen engagement and improve discovery quality based on
  what early users actually do, rather than what the team guessed they
  would do
- **Likely Themes** (to be confirmed with data):
  - Recommendation quality improvements (signal from reads, replies, follows)
  - Threaded discussion / commenting depth
  - Notifications and follow graph
  - Moderator tooling improvements based on real moderation load

## Constraints & Risks

### Constraints

- **Timeline**: 2-3 months to launch
- **Moderation**: Capacity (recruiting and supporting moderators) and the
  technical challenge of detecting AI-generated, NSFW, and hateful
  content reliably
- **Tech stack fixed**: Google Cloud, Neon Postgres, FastAPI

### Risks

- **Cold-start problem**: Recommendations need a critical mass of posts
  and signal before they are useful — early users may see a sparse feed
- **AI-generated content detection**: Current classifiers are
  unreliable; moderation policy must combine automated signals with
  human review
- **Differentiator depends on community quality**: The "smaller, more
  enjoyable atmosphere" is a function of moderation rigor, not
  technology — investment must match the claim
