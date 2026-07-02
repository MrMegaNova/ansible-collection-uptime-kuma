# Changelog

## 0.6.0 (2026-07-02)

- New `info` module: read-only gathering of monitors, status pages, notifications,
  tags and maintenance windows, with an optional `gather` filter.
- `maintenance` module: new `state: paused`, which ensures the window exists but
  is paused and keeps its scope in sync without resetting the time window.

## 0.5.0 (2026-07-02)

- New `monitor` module: create, update and delete monitors. Common fields are
  exposed directly, anything else via a free-form `settings` dict; optional
  `notifications` assignment by name. Idempotent, supports check mode.
- New `notification` module: create, update and delete notifications. Type-specific
  configuration passed through `settings`. Idempotent, supports check mode.
- New `status_page` module: create, update and delete status pages, including the
  monitors shown on the page. Idempotent, supports check mode.
- `module_utils`: the Socket.IO client now reads a status page's public JSON
  (`/api/status-page/<slug>`) so status page updates preserve the monitor layout.

## 0.4.0 (2026-07-02)

- New `tag` module: create, update (colour) and delete Uptime Kuma tags.
  Idempotent, supports check mode.
- Connection options (`api_url`, `api_username`, `api_password`, `api_mfa_token`,
  `api_timeout`) are now provided by a shared documentation fragment
  (`mrmeganova.uptime_kuma.connection`) and a `connection_argument_spec()` helper,
  so every module exposes them consistently.
- Added the `uptime_kuma` action group, so `module_defaults` can set the
  connection options once for every module of the collection.

## 0.3.0 (2026-07-02)

- `maintenance` module: the window can be attached to status pages via
  `status_pages` (by title or slug) or `all_status_pages: true` for all of them.
  Idempotent assignment.

## 0.2.0 (2026-07-02)

- `maintenance` module: switches to a self-expiring window (`single` strategy,
  `duration_minutes`) instead of the enable/disable `manual` pair. The window is
  created before the update, persists across an Uptime Kuma restart (which may run
  on the affected host) and expires on its own — no more API calls after the
  reboot. The `active`/`state: paused` options were removed.

## 0.1.0 (2026-07-02)

- `maintenance` module: manage maintenance windows in `manual` strategy (creation,
  monitor assignment by name, enable/disable, deletion). Tested against Uptime
  Kuma 2.4.0.
