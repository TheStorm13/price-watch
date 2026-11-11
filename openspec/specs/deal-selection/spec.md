# deal-selection Specification

## Purpose

Defines deal eligibility using the primary variant's two-year time-weighted price baseline.

## Requirements

### Requirement: Two-year time-weighted average and extrema
The system SHALL calculate averagePrice as sum(price × duration) / sum(duration)
within the last two calendar years in UTC. The start SHALL retain the UTC time
of day; February 29 SHALL clamp to February 28 when needed. Only in-stock,
non-null price intervals with positive duration SHALL contribute weight.
Unknown, out-of-stock and unpriced states SHALL terminate the preceding interval
and SHALL NOT contribute to either sum. Future observations SHALL be excluded.

Each state SHALL last until the next observation; the final state SHALL last
until calculation time, including gaps in collection. Observations SHALL be
ordered by observed_at then ID. The last state before the window SHALL be carried
into the window, clipped at its start. The system SHALL NOT extrapolate before
the first observation. Repeated unchanged observations SHALL NOT change the mean.
The result SHALL be null without positive valid duration, otherwise rounded to
12 decimal places, ties away from zero, without binary floating-point money.

minimumPrice and maximumPrice SHALL cover the same two-year window, including
states carried across its start and valid observations at calculation time.
Superseded states ending at or before the window start SHALL be excluded.
Saved history SHALL NOT be deleted to enforce the window.
baselineDays SHALL count UTC dates with saved valid observations inside the
window, excluding a carried observation before it; it SHALL NOT represent coverage.

#### Scenario: A short price spike
- **WHEN** a price of 1000 lasted 29 days and 3000 lasted one day, with no earlier known price in the window
- **THEN** averagePrice is 1066.666666666667, minimumPrice is 1000, and maximumPrice is 3000

#### Scenario: Carried state
- **WHEN** the last state before the window is an in-stock price of 100 and there are no subsequent observations
- **THEN** the mean, minimum and maximum are 100 and baselineDays is 0

#### Scenario: Missing availability
- **WHEN** 100 lasted one day, an unavailable state lasted four days, and 200 lasted one day
- **THEN** the mean is 150, excluding the unavailable interval

### Requirement: Deal eligibility uses the time-weighted baseline
The system SHALL offer a card as a deal when participation is enabled, its latest
observation is in stock with a price, a time-weighted average exists, and current
price is below that average. Savings SHALL be average minus current price.
Card creation time and baselineDays SHALL NOT add an eligibility threshold.

#### Scenario: A new lower price has no duration yet
- **WHEN** the previous known price is 100 and a latest price of 80 is recorded at calculation time
- **THEN** the baseline remains 100 and savings are 20

#### Scenario: Empty or zero-duration baseline
- **WHEN** no priced interval has positive duration
- **THEN** averagePrice is null and the card is not a deal

#### Scenario: Other deal conditions
- **WHEN** participation is disabled, the latest state is unavailable/unpriced, or current price is at least the mean
- **THEN** the card is not a deal

### Requirement: Detail statistics are independent of the history period
History statistics SHALL cover the two-year window and expose windowStart and
windowEnd instead of a selected days value. The history days parameter SHALL
only change returned measurement rows, their count and pagination. The 7/30/90
selector SHALL also control the chart, but SHALL NOT change the upper statistics.
The upper block SHALL retain minimum, maximum, range midpoint and range difference;
the range midpoint SHALL NOT be presented as the time-weighted average.

#### Scenario: Switching the history period
- **WHEN** the user changes 30 days to 7 or 90 days
- **THEN** chart and measurement rows use the selected period and the upper statistics retain their two-year scope
