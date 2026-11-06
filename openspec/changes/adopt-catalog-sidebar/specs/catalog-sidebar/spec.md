## ADDED Requirements

### Requirement: Permanent application sidebar
The application SHALL use the approved 260 px left sidebar on the normal catalog and detail routes, with a noninteractive Price watch brand. It SHALL expose global add, refresh, group creation, import/export, real desktop Chrome and background settings actions. The sidebar middle SHALL scroll independently and its single collection progress panel SHALL appear at the bottom right of the window. Existing service retry, validation, pending states and errors SHALL remain available.

#### Scenario: Collection panel geometry
- **WHEN** a collection run is visible
- **THEN** its panel is 490 px wide with 28 px right/bottom insets and a maximum height of calc(100dvh - 56px)

#### Scenario: Add from details
- **WHEN** the user opens add from product details
- **THEN** the drawer opens on the left and closing it restores the details screen and trigger focus

#### Scenario: Desktop tools
- **WHEN** the user opens Chrome or changes background settings
- **THEN** the existing desktop commands run and errors remain visible without replacing the current route

### Requirement: Unified catalog filters
The sidebar SHALL offer default deals-first or ascending/descending price sorting, multiple marketplaces (at least one), an only-in-stock checkbox, OR tags and all/deals/non-deals selection. Defaults SHALL include all marketplaces and products; no selected tags SHALL mean untagged products. Missing stock SHALL be excluded by only-in-stock. Search SHALL match names/external articles; internal ID and column/update sorting SHALL be excluded.

#### Scenario: Filter layout
- **WHEN** the user views the catalog
- **THEN** sidebar filters appear in order: stock, sorting, deal status, marketplaces, tags; reset appears to the right of the view switcher when conditions are active and preserves the selected view

#### Scenario: Combined filters
- **WHEN** marketplaces, tags and stock conditions are enabled
- **THEN** each matching card satisfies all conditions and its internal database ID is not searched

### Requirement: Compact filter popovers
Checkbox popovers SHALL match their trigger width, contain individual options without duplicate headings, and expose a left content-width bulk button. Tags SHALL allow clearing all; marketplaces SHALL retain at least one selection.

#### Scenario: Bulk selection
- **WHEN** all tags or marketplaces are selected
- **THEN** the bulk action clears tags or retains one marketplace; with partial selection it selects every option

#### Scenario: Mixed filter conditions
- **WHEN** the user selects two marketplaces, tags and only-in-stock
- **THEN** each matching product satisfies the whole combination and the selections survive reload

#### Scenario: Details filter action
- **WHEN** the user changes a sidebar catalog filter while viewing details
- **THEN** the catalog opens with the saved context plus the changed filter

### Requirement: Catalog heading and counts
The heading SHALL be Карточки товаров with one adjacent Выбрано n из m товаров count of matching and total individual cards, including members once. Bulk checkboxes and collapsed groups SHALL NOT affect it. View controls SHALL be left aligned. The compact equal-width list and tile typography SHALL follow the approved implementation checklist.

#### Scenario: Collapse and selection
- **WHEN** the user collapses a group or selects cards for bulk operations
- **THEN** the product count remains unchanged

### Requirement: Permanent runtime path
The approved UI SHALL run without demo environment variables or sidebar query switches. Fake settings, duplicate models, superseded header/filters and demo UI gates SHALL be removed. Test fixtures SHALL remain isolated from desktop data.

#### Scenario: Ordinary launch
- **WHEN** the desktop application opens the catalog
- **THEN** the sidebar uses real API data and the existing collection and desktop runtime providers
