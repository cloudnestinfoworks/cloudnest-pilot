# Architecture

How OCP Agent is structured and how to extend it.

## The agent loop (mental model)

```
┌──────────┐   user types:                ┌──────────────┐
│   User   │  "deploy cluster on AWS"  →  │ AgentSession │
└──────────┘                              │  (core.py)   │
     ↑                                     └──────┬───────┘
     │                                            │
     │                        send to Claude API  │
     │                                            ↓
     │                              ┌────────────────────────┐
     │                              │        Claude          │
     │                              │ decides: text OR tool? │
     │                              └───────┬────────────────┘
     │                                      │
     │      ┌───────────────────────────────┤
     │      ↓                               ↓
┌──────────────┐                  ┌────────────────────┐
│ show text to │                  │   Tool requested   │
│    user      │                  └─────┬──────────────┘
└──────────────┘                        │
                                        ↓
                              ┌──────────────────────┐
                              │ Requires confirm?    │
                              └──┬────────────────┬──┘
                                 │ yes            │ no
                                 ↓                ↓
                          ┌──────────────┐  ┌──────────┐
                          │ Ask user     │  │   Run    │
                          │ y/n          │  │ directly │
                          └──┬────────┬──┘  └─────┬────┘
                             │        │           │
                             ↓        ↓           ↓
                          run it   deny it    send result back to Claude
                             │        │           │
                             └────────┴───────────┘
                                      │
                                      ↓
                              loop to Claude until
                              stop_reason = end_turn
```

## File-by-file

### `run.py`

Entry point. Parses `--cli` or `--web`, loads config, dispatches.

### `ocp_agent/config.py`

Reads `.env` and environment variables. Validates `ANTHROPIC_API_KEY`.
Creates `~/.ocp-agent/clusters/` and `~/.ocp-agent/history.log` on first run.

### `ocp_agent/core.py`

**The heart.** `AgentSession` encapsulates one conversation:
- `send_user_message(text)` → `TurnResult`
- `continue_after_confirmation(approved, denied)` → `TurnResult`

`_model_turn()` is the recursive loop:
1. Call Claude
2. For each content block Claude returned:
   - `text` → add to TurnResult.texts
   - `tool_use` → either pending (needs confirmation) or auto (runs now)
3. If auto tools ran, recurse so Claude sees results and continues

### `tools/registry.py`

Tool registration and discovery. The `@tool(...)` decorator adds a function
to the registry. `tools_for_claude()` formats the registry for the Messages
API.

### `tools/shell.py`

`run_shell` — execute any command with a timeout. Requires confirmation.
Has a hard-coded blocklist of catastrophic patterns (`rm -rf /`, fork bombs,
disk erasure) that are refused even if the user approves.

### `tools/filesystem.py`

`read_file` (safe) and `write_file` (confirmed). Path expansion via `~`.

### `tools/aws.py`

`check_aws` — validates credentials, region, Route53 zone, and EC2 quota.
Read-only, no confirmation needed.

### `tools/ocp.py`

`list_clusters` — scans `~/.ocp-agent/clusters/` for installed clusters.
`get_cluster_status` — runs `oc get nodes`, `oc get co`, `oc get pods` against
a specific cluster's kubeconfig.

### `ocp_agent/cli.py`

Rich-formatted terminal UI. Uses `rich.prompt.Prompt` for interactive input
and `rich.syntax.Syntax` for syntax-highlighted previews of shell commands
and YAML files.

### `ocp_agent/web.py`

Flask backend with three routes:
- `GET /` — serves `chat.html`
- `POST /api/chat/message` — proxy to `AgentSession.send_user_message`
- `POST /api/chat/confirm` — proxy to `continue_after_confirmation`
- `GET /api/clusters` — sidebar data

Session state kept in-memory keyed by a cookie. Not intended for multi-user.

### `web/templates/chat.html`

Single-page UI. Dark theme with burnt-orange accent. No frontend framework —
just vanilla JS.

### `web/static/app.js`

Handles:
- Rendering user/agent messages
- Showing confirmation cards for pending tools
- Approving / denying
- Periodic refresh of the cluster sidebar

## How to add a new tool

Say you want to add `check_gcp` for Google Cloud pre-flight checks.

1. Create `tools/gcp.py`:

```python
from .registry import tool

@tool(
    name="check_gcp",
    description="Validate GCP project, service account, and region for OpenShift.",
    input_schema={
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "region": {"type": "string"},
        },
        "required": ["project_id", "region"],
    },
    requires_confirmation=False,
)
def check_gcp(project_id: str, region: str) -> str:
    # ... implementation ...
    return "check result"
```

2. Import it in `ocp_agent/core.py` at the top:

```python
from tools import shell, filesystem, aws, ocp, gcp  # add gcp
```

3. Done. Claude will see `check_gcp` in its tool list on the next turn.

## How to change the system prompt

`SYSTEM_PROMPT` in `ocp_agent/core.py`. Edit and restart. It's the same
prompt for every conversation, so changes here affect everything.

Keep the existing rules about safety and confirmation — those are load-bearing.

## How to change the model

Edit `.env`:

```
ANTHROPIC_MODEL=claude-opus-4-5-20250514
```

Or set `ANTHROPIC_MODEL` in your shell. Options:
- `claude-sonnet-4-*` (balanced, default)
- `claude-opus-4-*` (smartest, more expensive)
- `claude-haiku-4-*` (fastest, cheapest — good for simple tool orchestration)

## Extending to other clouds (Azure, GCP)

The tool dispatch is cloud-agnostic — only `check_aws` is AWS-specific.

For Azure, you'd add:
- `tools/azure.py` with `check_azure(subscription_id, resource_group, region)`
- A convention for where installer binaries live
- Update the system prompt to mention Azure capabilities

Claude figures out which tool to call based on what the user asks.

## Conversation persistence (future)

Currently conversations are in-memory — restart the process, history is
gone. To persist:

1. Add SQLite via `sqlalchemy` or `sqlite3` directly
2. Serialize `AgentSession.messages` on every turn
3. Add a `/api/chat/history/<id>` endpoint

Not in v1 because the agent is stateful via the filesystem (kubeconfigs,
cluster dirs) — you don't usually need to resume a conversation mid-install.

## Testing

Currently manual — run the tool, interact with it. For real tests:

1. Mock the `Anthropic` client in `core.py` to return fixed responses
2. Unit-test individual tools by calling their functions directly
3. Integration-test the full loop with a recorded Claude response

The skeleton for tests would go in `tests/` but isn't built yet.
