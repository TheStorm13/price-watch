# 0013: Selective recurring variant tracking

Status: Accepted; implementation accepted by the user on 2026-11-04.

The user approved initial discovery of every variant with recurring tracking disabled for extras on Ozon, Wildberries and AliExpress. The primary always tracks; individual and bulk controls preserve history.

Store independent default-false preferences on variants, and an initial discovery purpose on runs. Effective tracking is primary OR preference. Capture ordinary targets at enqueue time. Initial runs expand the family and collect initial prices; ordinary runs retain newly discovered metadata without collecting disabled extras. Bulk controls apply to known non-primary variants only. Switching primary does not mutate preferences.

Creation and initial queue insertion share a PostgreSQL transaction. Reuse the existing queue and executor rather than fetching synchronously in an HTTP request or relying on a frontend callback. Desktop prepares the collector before creating; worker and CLI use the same persisted jobs. Existing queued targets and history are retained. Import preserves existing local preferences and restores preferences for new imported variants.

Alternatives rejected: a card-wide boolean cannot express individual choices; frontend-only refresh can be lost after successful creation; synchronous creation blocks on remote pages and CAPTCHA. No second queue or collector is introduced.

This supersedes recurring-all scheduling in ADR 0012; membership discovery, exact identity, limits and ownership remain unchanged.
