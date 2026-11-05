## Purpose

Allow users to evaluate the chosen sidebar arrangement of a single price catalog on isolated sample data before adopting it in the desktop application.

## ADDED Requirements

### Requirement: Isolated sidebar preview
The preview SHALL use mock data and the selected second layout. It SHALL NOT invoke desktop services or replace the normal desktop layout. The superseded comparison switcher SHALL be absent.

#### Scenario: Open the preview
- **WHEN** the demo server opens the catalog
- **THEN** the selected sidebar layout is visible and the interface identifies the data as demo data

### Requirement: Single catalog with search above results
The catalog SHALL show «Карточки товаров» above name/marketplace-article search, with no subtitle. Its matching/total count SHALL appear only to the right of that heading as «Выбрано n из m товаров». Search SHALL remain above list or grid results. Group creation and filters SHALL be in the sidebar. Filters and view SHALL survive reload and return from details.

#### Scenario: Search by article
- **WHEN** a user enters a marketplace article in the search field above results
- **THEN** matching products are shown without searching internal database identifiers

#### Scenario: Count beside heading
- **WHEN** catalog filters change the matching results
- **THEN** one counter beside the heading updates and no duplicate count appears below the search

### Requirement: Compact uniform catalog rows
The preview SHALL place list/grid controls at the left above results. Its list SHALL use a shared compact column grid without stretching rows to fill wide screens. All product and group rows SHALL have the same width. Selection checkboxes SHALL precede product photos between the row's left edge and photo. The marketplace column SHALL show only its mark, retaining an accessible name and hover title.

#### Scenario: Wide and narrow screens
- **WHEN** the user views the catalog at different desktop widths
- **THEN** rows keep equal widths and aligned columns, with horizontal scrolling contained within the list when necessary

### Requirement: Multiple marketplace and tag selection
Marketplace and tag controls SHALL allow multiple selections and default to all. At least one marketplace SHALL remain selected. Nonempty selected tags SHALL match at least one product tag. All tags SHALL include untagged products. Empty tags SHALL display «Без тегов» and match only untagged products.

#### Scenario: Two distinct tags
- **WHEN** two tags are selected
- **THEN** products with either tag are included and products with neither are excluded

#### Scenario: Last marketplace
- **WHEN** only one marketplace is selected
- **THEN** it cannot be unchecked until another is selected

#### Scenario: Untagged products
- **WHEN** the user clears all tag checkboxes and reloads the page
- **THEN** the field displays «Без тегов» and only untagged products match

### Requirement: Left-side card creation
The preview's add-card action SHALL open its form from the left edge, including when invoked from product details. Closing SHALL restore focus to the invoking control.

#### Scenario: Add from product details
- **WHEN** a user invokes «Добавить карточку» from product details in the preview
- **THEN** the form opens at the left edge and closing it returns focus to the action

### Requirement: Compact multi-selection popups
The closed controls SHALL display «Все маркетплейсы» or «Все теги» when all options are selected. Popups SHALL show only individual option checkboxes and a bulk button, without repeated visible headings. The button SHALL select all when partial; when all are selected, it SHALL clear tags or keep one marketplace, with labels describing those actions.

#### Scenario: Bulk actions
- **WHEN** all tags or marketplaces are selected
- **THEN** the buttons display «Снять выбор» for tags and «Оставить один» for marketplaces, and change to «Выбрать все» after use

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
