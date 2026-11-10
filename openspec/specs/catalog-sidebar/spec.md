# catalog-sidebar Specification

## Purpose

Defines the permanent application sidebar, unified catalog controls, product counts and access to global desktop actions.

## Requirements

### Requirement: Permanent application sidebar
The application SHALL use the approved 260 px left sidebar on the normal catalog and detail routes, with a noninteractive Price watch brand. It SHALL expose global add, refresh, group creation, real desktop Chrome and a settings action. The sidebar middle SHALL scroll independently and its single collection progress panel SHALL appear at the bottom right of the window. Existing service retry, validation, pending states and errors SHALL remain available.

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
The sidebar SHALL offer default deals-first or ascending/descending price sorting, multiple marketplaces (at least one), an only-in-stock checkbox, OR tags and all/participating/deals/non-deals selection. A default-on participation-first checkbox SHALL appear under the Sorting heading before its selector; enabled products SHALL precede disabled products before the selected sort. Defaults SHALL include all marketplaces and products; no selected tags SHALL mean untagged products. Missing stock SHALL be excluded by only-in-stock. Search SHALL match names/external articles; internal ID and update sorting SHALL be excluded.

#### Scenario: Column sorting
- **WHEN** the user clicks a data column header
- **THEN** that column toggles ascending/descending sorting with a visible direction and synchronized sidebar/URL; explicit sorts have no deal-eligibility priority; participation priority follows the checkbox and missing money stays last within each participation block

#### Scenario: Filter layout
- **WHEN** the user views the catalog
- **THEN** sidebar filters appear in order: stock, Sorting heading, participation-first checkbox, sorting selector, deal status, marketplaces, tags; reset appears to the right of the view switcher when conditions are active and preserves the selected view

#### Scenario: Combined filters
- **WHEN** marketplaces, tags and stock conditions are enabled
- **THEN** each matching card satisfies all conditions and its internal database ID is not searched

#### Scenario: Participating products filter
- **WHEN** the second deal-filter option «Участвуют» is selected
- **THEN** only products enabled for deal selection remain, including currently nonprofitable products; group members are checked individually

#### Scenario: Default participation order and reset
- **WHEN** the catalog opens with default controls
- **THEN** the checkbox «Сначала участвующие» is checked and products are ordered by participation, then descending savings

#### Scenario: Disable participation priority
- **WHEN** the user clears the checkbox and chooses a column sort
- **THEN** that column orders all products together; the opt-out survives reload and details return, and reset restores the checked default while retaining view

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
The heading SHALL be «Товары» with an adjacent «n товаров» count without active filters or «n из m» with filters. Counts SHALL include each matching/total individual product once, including group members. Bulk checkboxes and collapsed groups SHALL NOT affect it. View controls SHALL be left aligned. The compact equal-width list and tile typography SHALL follow the approved implementation checklist.

#### Scenario: Collapse and selection
- **WHEN** the user collapses a group or selects cards for bulk operations
- **THEN** the product count remains unchanged

### Requirement: Permanent runtime path
The approved UI SHALL run without demo environment variables or sidebar query switches. Fake settings, duplicate models, superseded header/filters and demo UI gates SHALL be removed. Test fixtures SHALL remain isolated from desktop data.

#### Scenario: Ordinary launch
- **WHEN** the desktop application opens the catalog
- **THEN** the sidebar uses real API data and the existing collection and desktop runtime providers

### Requirement: Settings beside the sidebar
Settings SHALL open as a separate accessible dialog panel whose left edge aligns with the sidebar right edge (260 px on desktop), with bounded width and height. Import/export and desktop background controls SHALL live inside it. Nested import cancellation SHALL return focus to its trigger in settings; successful transfer SHALL close settings and display its result in the shell. Demo mode SHALL NOT invoke native settings commands.

#### Scenario: Import from details
- **WHEN** the user opens settings from a product and cancels import
- **THEN** the product route remains unchanged and focus returns to Import inside settings

### Requirement: Compact controls and isolated scrolling
Sidebar filter triggers SHALL retain their width with a compact height around 32 px. Scrolling tags and analogous dropdowns SHALL NOT scroll the catalog at either edge, and normal catalog scrolling SHALL resume after closing. Header sort arrows SHALL follow the text; contextual help SHALL be a separate control that does not sort.

#### Scenario: End of tags
- **WHEN** the user continues scrolling at the bottom of the tag popup
- **THEN** catalog scroll position remains unchanged
