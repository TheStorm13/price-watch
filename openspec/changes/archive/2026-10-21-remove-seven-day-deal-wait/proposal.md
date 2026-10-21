# Proposal

## Why

The deal list currently excludes a card until seven days after it was created, even when its saved price history already shows a meaningful price drop. Remove that waiting period so a new card can qualify as soon as there is a previous price to compare.

## What Changes

- Remove the card creation age condition from deal selection in the PostgreSQL API and demo mock API.
- Keep the existing real API deal requirements: participation enabled, latest observation in stock with a price, at least one previous valid price observation, and latest price below the average of previous daily averages.
- Add coverage for a recently created card and update the deal behavior guide.

## Capabilities

### New Capabilities

- `deal-selection`: Defines when saved price observations qualify a card for the deal list.

### Modified Capabilities

None.

## Impact

The `/api/cards/deals` result and demo deal list may include recently created cards. No schema, API shape, stored history, migration, dependency, collection, CLI, or database-free JSON mode change is planned. Existing clients can handle the newly eligible results.
