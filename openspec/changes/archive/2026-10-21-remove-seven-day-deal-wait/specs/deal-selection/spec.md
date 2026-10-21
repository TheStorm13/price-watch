# Spec Delta

## Purpose

Defines when a tracked product qualifies as a deal based on its current availability and saved price history.

## ADDED Requirements

### Requirement: Deal eligibility uses prior prices without a card age threshold
The system SHALL offer a card as a deal when deal participation is enabled, its latest observation is in stock with a price, at least one earlier valid price observation exists, and its latest price is below the average of daily averages from earlier valid observations. The card's creation time SHALL NOT affect eligibility.

#### Scenario: Recently created card with a lower current price
- **WHEN** a recently created card has a previous valid price observation and a lower latest in-stock price
- **THEN** the card appears in the deal list immediately

#### Scenario: Card has no previous valid price
- **WHEN** a card has only its latest valid price observation
- **THEN** the card does not appear in the deal list

#### Scenario: Other deal conditions still apply
- **WHEN** a card is excluded from deals, its latest observation is unavailable or unpriced, or its latest price is not below the prior daily average
- **THEN** the card does not appear in the deal list
