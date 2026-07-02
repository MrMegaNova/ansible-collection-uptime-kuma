# Changelog

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
