# Spec Delta

## MODIFIED Requirements

### Requirement: Unified catalog filters
The sidebar SHALL offer default deals-first or ascending/descending price sorting, multiple marketplaces (at least one), an only-in-stock checkbox, OR tags and all/participating/deals/non-deals selection. A default-on participation-first checkbox SHALL follow stock; enabled products SHALL precede disabled products before the selected sort. Defaults SHALL include all marketplaces and products; no selected tags SHALL mean untagged products. Missing stock SHALL be excluded by only-in-stock. Search SHALL match names/external articles; internal ID and update sorting SHALL be excluded.

#### Scenario: Column sorting
- **WHEN** the user clicks a data column header
- **THEN** that column toggles ascending/descending sorting with a visible direction and synchronized sidebar/URL; explicit sorts have no deal-eligibility priority; participation priority follows the checkbox and missing money stays last within each participation block

#### Scenario: Filter layout
- **WHEN** the user views the catalog
- **THEN** sidebar filters appear in order: stock, participation-first checkbox, sorting, deal status, marketplaces, tags; reset appears to the right of the view switcher when conditions are active and preserves the selected view

#### Scenario: Combined filters
- **WHEN** marketplaces, tags and stock conditions are enabled
- **THEN** each matching card satisfies all conditions and its internal database ID is not searched

#### Scenario: Participating products filter
- **WHEN** the second deal-filter option «Участвуют в выгодных предложениях» is selected
- **THEN** only products enabled for deal selection remain, including currently nonprofitable products; group members are checked individually

#### Scenario: Default participation order and reset
- **WHEN** the catalog opens with default controls
- **THEN** the checkbox «Сначала товары, участвующие в выгодных предложениях» is checked and products are ordered by participation, then descending savings

#### Scenario: Disable participation priority
- **WHEN** the user clears the checkbox and chooses a column sort
- **THEN** that column orders all products together; the opt-out survives reload and details return, and reset restores the checked default while retaining view
