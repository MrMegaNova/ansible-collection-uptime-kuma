=====================================
mrmeganova.uptime\_kuma Release Notes
=====================================

.. contents:: Topics

v0.7.1
======

Release Summary
---------------

Makes the maintenance module resilient to flaky scope-read Socket.IO acks on existing windows.

Bugfixes
--------

- maintenance module no longer fails when the scope-read Socket.IO calls (``getMonitorMaintenance``, ``getMaintenanceStatusPage``) time out on an already-existing window; since the matching set calls are idempotent, the scope is simply re-applied instead of failing the task.

v0.7.0
======

Release Summary
---------------

Adds diff mode to the mutating modules and moves changelog management to
antsibull-changelog fragments.

Minor Changes
-------------

- All mutating modules (maintenance, tag, notification, monitor, status_page) now support diff mode; run with ``--diff`` to preview the before/after state.
- The changelog is now generated from ``changelogs/fragments/`` with antsibull-changelog instead of being edited by hand.

v0.6.0
======

Minor Changes
-------------

- New info module for read-only gathering of monitors, status pages, notifications, tags and maintenance windows.
- maintenance module gains ``state=paused``, which ensures the window exists but is paused and keeps its scope in sync without resetting the time window.

v0.5.0
======

Minor Changes
-------------

- New monitor module to create, update and delete monitors.
- New notification module to create, update and delete notifications.
- New status_page module to create, update and delete status pages, including the monitors shown on the page.

v0.4.0
======

Minor Changes
-------------

- Added the ``uptime_kuma`` action group, so ``module_defaults`` can set the connection options once for every module.
- Connection options are now provided by a shared documentation fragment (``mrmeganova.uptime_kuma.connection``) and a ``connection_argument_spec()`` helper.
- New tag module to create, update and delete Uptime Kuma tags.

v0.3.0
======

Minor Changes
-------------

- maintenance module can attach the window to status pages via ``status_pages`` (by title or slug) or ``all_status_pages``. Idempotent assignment.

v0.2.0
======

Minor Changes
-------------

- maintenance module switches to a self-expiring window (``single`` strategy, ``duration_minutes``) instead of the enable/disable ``manual`` pair. The window persists across an Uptime Kuma restart and expires on its own.

v0.1.0
======

Release Summary
---------------

Initial release.

Minor Changes
-------------

- maintenance module to manage maintenance windows in the ``manual`` strategy (creation, monitor assignment by name, enable/disable, deletion). Tested against Uptime Kuma 2.4.0.
