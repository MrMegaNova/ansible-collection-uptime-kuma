# mrmeganova.uptime_kuma

Minimal Ansible collection to drive Uptime Kuma **2.x** through its Socket.IO API
(there is no REST API, and community libraries cap out at Uptime Kuma 1.23.x).

## Requirements

- The `python-socketio` and `websocket-client` Python packages on the controller
  (see the repo `pyproject.toml`).
- Username/password authentication: Uptime Kuma API keys only grant access to the
  Prometheus metrics endpoint, not to the Socket.IO API.

## Modules

### `mrmeganova.uptime_kuma.maintenance`

Opens a **self-expiring** maintenance window (`single` strategy) covering a set of
monitors: it starts immediately, lasts `duration_minutes`, then ends on its own. It
persists across an Uptime Kuma restart (which may run on the affected host), so no
"teardown" call is needed after a reboot. Idempotent (unchanged as long as the window
is active and the scope identical), supports `--check`.

```yaml
- name: Open the maintenance window before the update
  mrmeganova.uptime_kuma.maintenance:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    title: "ansible-update srv-01"
    monitors:
      - srv-01 http
      - srv-01 ping
    all_status_pages: true      # or status_pages: [Public, internal]
    duration_minutes: 45
  delegate_to: localhost
```

### `mrmeganova.uptime_kuma.tag`

Manages tags (create, update colour, delete). Identified by `name`, idempotent,
supports `--check`.

```yaml
- name: Ensure a "production" tag exists
  mrmeganova.uptime_kuma.tag:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    name: production
    color: "#059669"
  delegate_to: localhost
```

## Sharing connection options

Every module takes the same connection options. Rather than repeating them, set
them once for the whole `uptime_kuma` action group with `module_defaults`:

```yaml
- hosts: localhost
  module_defaults:
    group/mrmeganova.uptime_kuma.uptime_kuma:
      api_url: https://status.example.org
      api_username: admin
      api_password: "{{ vault_kuma_password }}"
  tasks:
    - name: Ensure a tag exists
      mrmeganova.uptime_kuma.tag:
        name: production
    - name: Open a maintenance window
      mrmeganova.uptime_kuma.maintenance:
        title: "ansible-update srv-01"
        monitors: [srv-01 http]
        duration_minutes: 45
```
