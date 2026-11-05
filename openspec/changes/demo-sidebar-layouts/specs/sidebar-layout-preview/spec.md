## Purpose

Allow users to compare two interactive sidebar arrangements of the same price catalog on isolated sample data before choosing the production layout.

## ADDED Requirements

### Requirement: Isolated sidebar preview
The preview SHALL use mock data and expose two switchable layouts. It SHALL NOT invoke desktop services or replace the normal desktop layout.

#### Scenario: Open the preview
- **WHEN** the demo server opens the catalog
- **THEN** layout 1 is visible and the interface identifies the data as demo data

### Requirement: Single catalog with alternative control placement
Both layouts SHALL use one catalog with the same interactions. Layout 1 SHALL keep search, filters, sorting and group creation in the catalog. Layout 2 SHALL place those controls in the sidebar. Switching SHALL preserve catalog filters and view.

#### Scenario: Compare an active filter
- **WHEN** a user filters the catalog and switches layouts
- **THEN** the same filter and results remain and the controls move to the selected location

### Requirement: Bottom anchored collection status
During collection the preview SHALL show the existing collection state at the very bottom of the sidebar across its full width. Scrolling filters SHALL NOT displace it. Verification continuation and terminal dismissal SHALL remain accessible.

#### Scenario: Verification in the narrow layout
- **WHEN** collection requests user verification at 1024×768 in layout 2
- **THEN** the panel remains inside the sidebar, its actions are reachable and continuation can complete the simulated run
