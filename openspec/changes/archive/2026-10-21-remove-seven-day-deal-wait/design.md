# Design

## Context

The PostgreSQL deal query filters `marketplace_cards.created_at` against a seven-day cutoff before comparing the latest price with earlier daily averages. The demo mock API has the same age test in its curated deal fixture. The UI consumes the existing deal response; collection and history storage do not apply this cutoff.

## Goals / Non-Goals

**Goals:** Remove the creation-age predicate in both deal providers while preserving the price comparison and response shape.

**Non-Goals:** Change how observations are collected or stored, change the baseline formula, or alter the demo fixture's set of illustrative deal cards.

## Decisions

- Delete only the age predicate and its unused time calculation from the PostgreSQL query. This keeps eligibility derived from existing history and requires no schema or data changes. Changing the baseline window instead would alter more deal behavior than requested.
- Remove the age condition from the demo mock's deal filter as well. The mock still uses a curated fixture rather than reproducing SQL aggregation; implementing aggregation there would expand scope and could change demo output beyond this request.
- Keep the `now` argument of `list_deals` for caller and test compatibility even though eligibility no longer needs it. Removing it would change a Python interface without benefiting users.

## Risks / Trade-offs

- A newly created card can qualify after two valid observations, including two on one calendar day. This is consistent with the current daily-average query; a targeted integration test will verify it.
- PostgreSQL integration testing requires a disposable `TEST_DATABASE_URL`. If unavailable, report that the database path remains unverified.

## Migration Plan

No migration or historical data rewrite is needed. Deploying the code changes the computed deal list on its next request. Rolling back restores the previous age filter.
