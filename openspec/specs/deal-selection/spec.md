# deal-selection Specification

## Purpose

Defines when a tracked product qualifies as a deal based on its current availability and saved price history.

## Requirements

### Requirement: Deal eligibility uses the full-history price range midpoint
The system SHALL offer a card as a deal when deal participation is enabled, its latest observation is in stock with a price, and its latest price is below `(minimum_price + maximum_price) / 2` over all saved in-stock, non-null prices of its primary variant, including the latest observation. Repeated observations SHALL NOT change this midpoint. `baselineDays` SHALL count days with valid prices across that entire history. The card's creation time SHALL NOT affect eligibility.

#### Scenario: Recently created card with a lower current price
- **WHEN** a recently created card has a previous valid price observation and a lower latest in-stock price
- **THEN** the card appears in the deal list immediately

#### Scenario: Card has no previous valid price
- **WHEN** a card has only its latest valid price observation
- **THEN** the card does not appear in the deal list

#### Scenario: Other deal conditions still apply
- **WHEN** a card is excluded from deals, its latest observation is unavailable or unpriced, or its latest price is not below the full-history range midpoint
- **THEN** the card does not appear in the deal list

#### Scenario: Repeated prices and a new maximum
- **WHEN** the saved valid prices are 100, 100 and 160
- **THEN** the catalog average price is 130 and the current price 160 is not a deal

#### Scenario: Current price is a new minimum
- **WHEN** the saved valid prices are 100 and 80
- **THEN** the average price is 90 and the savings are 10
