## Purpose

Allow users to evaluate the chosen sidebar arrangement of a single price catalog on isolated sample data before adopting it in the desktop application.

## ADDED Requirements

### Requirement: Isolated sidebar preview
The preview SHALL use mock data and the selected second layout. It SHALL NOT invoke desktop services or replace the normal desktop layout. The superseded comparison switcher SHALL be absent.

#### Scenario: Open the preview
- **WHEN** the demo server opens the catalog
- **THEN** the selected sidebar layout is visible and the interface identifies the data as demo data

### Requirement: Single catalog with search above results
The catalog SHALL omit its title/subtitle and show name/marketplace-article search above list or grid results. Group creation and filters SHALL be in the sidebar. Filters and view SHALL survive reload and return from details.

#### Scenario: Search by article
- **WHEN** a user enters a marketplace article in the search field above results
- **THEN** matching products are shown without searching internal database identifiers

### Requirement: Multiple marketplace and tag selection
Marketplace and tag controls SHALL allow multiple selections and default to all. Selected tags SHALL match at least one tag on the product. All tags SHALL include untagged products. An explicitly empty selection SHALL show no matches.

#### Scenario: Two distinct tags
- **WHEN** two tags are selected
- **THEN** products with either tag are included and products with neither are excluded

### Requirement: Availability and deal filters
Availability SHALL be one checkbox labelled «Только в наличии». Unchecked SHALL include all availability states; checked SHALL exclude unavailable and unknown products. Deal choices SHALL be «Все предложения», «Выгодные», «Невыгодные».

#### Scenario: Unknown availability
- **WHEN** «Только в наличии» is checked
- **THEN** products without availability data are excluded along with unavailable products

### Requirement: Three sorting choices
Sorting SHALL be the first sidebar filter with «Сначала выгодные» as default, «Сначала дешёвые» and «Сначала дорогие». Explicit price order SHALL apply across all matching products, with unknown prices last. Update-date and additional header sorts SHALL be absent in the preview.

#### Scenario: Cheapest first
- **WHEN** ascending price order is selected
- **THEN** a cheaper non-deal precedes a more expensive deal and products without prices appear last

### Requirement: Bottom anchored collection status
During collection the preview SHALL show the existing collection state at the very bottom of the sidebar across its full width. Scrolling filters SHALL NOT displace it. Verification continuation and terminal dismissal SHALL remain accessible.

#### Scenario: Verification in the narrow layout
- **WHEN** collection requests user verification at 1024×768 in layout 2
- **THEN** the panel remains inside the sidebar, its actions are reachable and continuation can complete the simulated run
