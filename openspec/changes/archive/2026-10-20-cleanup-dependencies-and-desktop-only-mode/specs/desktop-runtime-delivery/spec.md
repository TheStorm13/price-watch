# Spec Delta

## Purpose

Defines how the application delivers its user interface through the desktop shell while retaining the local API and command-line execution paths.

## ADDED Requirements

### Requirement: Desktop UI delivery
The system SHALL provide the production user interface through the desktop application and SHALL require a desktop service connection before live UI requests.

#### Scenario: Desktop startup
- **WHEN** the desktop application opens its UI
- **THEN** it starts or reconnects to local services and uses the assigned API endpoint and token for live requests

#### Scenario: Desktop service unavailable
- **WHEN** local services cannot start
- **THEN** the UI presents a recoverable startup error instead of sending live requests to a browser-relative endpoint

### Requirement: No standalone live browser UI
The system SHALL NOT offer a standalone browser UI connected to the live API. It SHALL retain a mock-backed browser fixture for automated UI tests.

#### Scenario: Live frontend development and build commands
- **WHEN** a developer uses documented live development or build commands
- **THEN** the resulting UI runs in the desktop shell without a separate live browser entry point

#### Scenario: Browser E2E fixture
- **WHEN** browser E2E tests run
- **THEN** they use a named mock-backed test fixture without requiring PostgreSQL or a live API

### Requirement: Local API and other execution paths remain available
The system SHALL preserve its local API for desktop and CLI consumers, worker collection, direct CLI collection, and database-free numeric Ozon JSON mode.

#### Scenario: CLI API
- **WHEN** the API CLI command is started with a database URL
- **THEN** its API routes remain available without a standalone browser UI

#### Scenario: Database-free product JSON
- **WHEN** a numeric Ozon ID is collected in JSON mode without `DATABASE_URL`
- **THEN** the command succeeds through its existing database-free path

### Requirement: Mode-specific verification
The project SHALL check the desktop build and service connection after each cleanup stage and SHALL keep the browser E2E suite for UI behavior checks.

#### Scenario: Cleanup stage verification
- **WHEN** an implementation stage changes dependencies or runtime wiring
- **THEN** relevant tests and a desktop build or startup check run, and browser E2E continues to pass
