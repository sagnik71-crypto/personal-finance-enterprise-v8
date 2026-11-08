# Changelog

All notable changes to **FinEnterprise V8** will be documented in this file.

## [8.1.0] - 2026-11-08
### Added
- Integrated **Gunicorn WSGI** production server configuration via `Procfile`.
- Added automated `/healthz` system monitoring endpoint for Render uptime checks.

### Changed
- Migrated default runtime execution from Flask development server to multi-worker Gunicorn architecture.

