## Why
Ozon groups variants with different SKU IDs. Users need complete initial discovery and independent price histories, while controlling recurring requests for Ozon, Wildberries and AliExpress.

## What Changes
- Adding a supported card atomically queues initial discovery and initial prices for every reachable variant.
- Additional variants default to tracking off, including existing data. The primary is always effectively tracked.
- Individual and bulk controls change recurring tracking without deleting metadata or history.
- Ordinary runs freeze their selected targets; initial discovery alone expands to all reachable variants. Newly discovered extras stay off.
- Transfer preserves explicit preferences. Numeric database-free mode remains one exact request.

## Impact
Database migration adds variant preferences and initial-discovery run purpose. API, worker, CLI, desktop form, variant page, transfer and demo share these contracts. Existing IDs, primary selection and history are preserved.
