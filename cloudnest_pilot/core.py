"""The agent brain.

Implements Anthropic's agent tool-use loop:
  1. User sends a message
  2. We send conversation + tool definitions to Claude
  3. Claude responds with either text (for user) or tool_use (for us to run)
  4. For confirmed-required tools, we call the UI's confirmation hook
  5. If approved, run the tool, send tool_result back to Claude
  6. Repeat until Claude stops asking for tools

The CLI and web UI both use this same AgentSession — they just implement
different confirm_callback and output_callback handlers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from anthropic import Anthropic
from anthropic.types import MessageParam

# Import tools - their @tool decorators register them.
# ruff: noqa: F401 — these are imported for side effects
from tools import aws, filesystem, ocp, shell
from tools.ocp import set_clusters_dir
from tools.registry import (
    all_tools,
    get_tool,
    tools_for_claude,
)
from tools.shell import set_history_log

from .config import Config


SYSTEM_PROMPT = """\
You are Cloudnest Pilot, a conversational AI assistant that helps the user deploy
and operate OpenShift clusters. You run LOCALLY on the user's laptop.

Your capabilities:
- Deploy new OpenShift clusters on AWS using the IPI (installer-provisioned
  infrastructure) method. Tooling: aws CLI, openshift-install binary.
- Manage existing clusters: check node health, scale workers, upgrade,
  troubleshoot pod/operator issues. Tooling: oc CLI.
- Generate install-config.yaml files from user-supplied parameters.

Rules:

1. SAFETY FIRST. You can propose shell commands via the run_shell tool,
   but the UI will show each command to the user for confirmation before
   executing. Propose what you need; the user will approve or deny.

2. SMALL STEPS. When deploying a cluster (which takes ~45 minutes), break
   the work into distinct, verifiable steps: pre-flight checks → generate
   config → run installer → verify health. Check the user understands each
   transition.

3. ASK, DON'T ASSUME. For any cluster deployment you need: cluster name,
   base domain, region, worker count, worker instance type, path to pull
   secret. Collect these one-by-one unless the user gave them upfront.
   Validate each against the user's AWS environment using check_aws.

4. BE A TEACHER. Explain what each step does briefly. The user is an
   OpenShift architect — they don't need hand-holding on concepts, but
   they appreciate reasoning for non-obvious choices.

5. FAIL HELPFULLY. When a tool returns an error (non-zero exit, exception,
   "command not found", missing file), DO NOT just dump stderr at the user.
   Instead:
   (a) Diagnose the root cause by reading the error carefully
   (b) Explain it in plain English that a tired engineer at 11pm can act on
   (c) Suggest specific, runnable fixes — not generic advice
   (d) Match severity to tone: missing tool / wrong path / no credentials
       are user-fixable; ask politely for the fix. Genuine bugs (segfault,
       panic, internal error) → ask the user to file a GitHub issue.

   Example translations:
   - "command not found: aws" → "Looks like AWS CLI isn't installed.
     Install from https://aws.amazon.com/cli/ then run `aws configure`."
   - "FileNotFoundError: pull-secret.json" → "Can't find your pull secret.
     Get one from https://console.redhat.com/openshift/install/pull-secret
     and save to ~/.ocp-agent/pull-secret.json."
   - "NoCredentialsError" → "AWS credentials aren't set up. Run
     `aws configure` and enter your access key + secret + region."

   Be matter-of-fact, not apologetic. The user knows you don't have feelings —
   skip "I'm sorry" preambles. Just diagnose and suggest fixes. Don't just regurgitate stderr.

6. CONTAIN YOUR ACTIONS. You are running on the user's personal laptop.
   You DO NOT run `rm -rf`, you DO NOT modify ~/.aws/credentials, you DO
   NOT install system packages. If something requires sudo, ask the user
   to run it themselves.

7. STATE PRESERVATION. Cluster installs save state to
   ~/.ocp-agent/clusters/<name>/. The openshift-install command writes
   auth/kubeconfig there on success. Never delete these directories — the
   user may need them to destroy clusters later.

Current context:
- OS: Detect the user's OS from their commands and paths. Windows uses
  backslash paths and tools like Git Bash; macOS/Linux use forward slash.
  When generating commands, match their OS conventions. Path examples in
  instructions use ~/foo (works on all OSes via home directory expansion).
- Running clusters: use list_clusters to see what's installed.
- The user is an experienced OpenShift architect — explain reasoning for
  non-obvious choices, but skip basic concept tutorials.
"""


@dataclass
class Message:
    """A message in the conversation. Either from user, from the assistant,
    or a tool result. Stored in a format that maps cleanly to Claude's API."""

    role: Literal["user", "assistant"]
    content: list[dict[str, Any]] | str


@dataclass
class PendingToolCall:
    """Claude asked to call a tool. We're waiting for user confirmation."""

    tool_use_id: str
    tool_name: str
    tool_input: dict[str, Any]


@dataclass
class TurnResult:
    """What happened after one turn of the conversation."""

    # Text messages to show the user (stop reasons, natural language).
    texts: list[str] = field(default_factory=list)
    # Tool calls awaiting confirmation. If non-empty, the UI needs to
    # prompt the user, then call continue_after_confirmation().
    pending_tools: list[PendingToolCall] = field(default_factory=list)
    # Tool results that ran automatically (no confirmation needed).
    auto_tool_results: list[dict[str, Any]] = field(default_factory=list)
    # True when Claude said "end_turn" — we should loop back to the user.
    end_turn: bool = False


class AgentSession:
    """A live conversation with the agent."""

    def __init__(self, config: Config):
        self.config = config
        self.client = Anthropic(api_key=config.anthropic_api_key)
        self.messages: list[MessageParam] = []

        # Wire tool dependencies.
        set_history_log(config.history_log)
        set_clusters_dir(config.clusters_dir)

    # ─────────────── Public API ───────────────

    def send_user_message(self, text: str) -> TurnResult:
        """User typed something. Get Claude's response."""
        self.messages.append({"role": "user", "content": text})
        return self._model_turn()

    def continue_after_confirmation(
        self,
        confirmed_calls: list[PendingToolCall],
        denied_calls: list[PendingToolCall],
    ) -> TurnResult:
        """Called by UI after user approves/denies tool calls."""

        # Build tool_result blocks for each call — run approved ones,
        # send "user denied" for the rest.
        result_blocks: list[dict[str, Any]] = []

        for call in confirmed_calls:
            tool_def = get_tool(call.tool_name)
            if tool_def is None:
                result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.tool_use_id,
                        "content": f"Unknown tool: {call.tool_name}",
                        "is_error": True,
                    }
                )
                continue
            try:
                output = tool_def.function(**call.tool_input)
                result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.tool_use_id,
                        "content": output,
                    }
                )
            except Exception as e:  # noqa: BLE001 - catch-all intentional
                result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.tool_use_id,
                        "content": f"Tool execution failed: {type(e).__name__}: {e}",
                        "is_error": True,
                    }
                )

        for call in denied_calls:
            result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.tool_use_id,
                    "content": "User denied this tool call. Try a different approach or ask the user for guidance.",
                    "is_error": True,
                }
            )

        # Append a single user-role message with all the tool_result blocks.
        self.messages.append({"role": "user", "content": result_blocks})

        return self._model_turn()

    # ─────────────── Internal ───────────────

    def _model_turn(self) -> TurnResult:
        """Call Claude once, process its response, return what happened."""

        response = self.client.messages.create(
            model=self.config.anthropic_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools_for_claude(),
            messages=self.messages,
        )

        # Record assistant response in conversation.
        assistant_blocks: list[dict[str, Any]] = []
        result = TurnResult()

        # Track auto tool calls so we can loop if any fire.
        auto_calls_to_run: list[PendingToolCall] = []

        for block in response.content:
            if block.type == "text":
                result.texts.append(block.text)
                assistant_blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_blocks.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
                call = PendingToolCall(
                    tool_use_id=block.id,
                    tool_name=block.name,
                    tool_input=dict(block.input),
                )
                tool_def = get_tool(block.name)
                if tool_def and tool_def.requires_confirmation:
                    result.pending_tools.append(call)
                else:
                    auto_calls_to_run.append(call)

        # Always append the assistant message so Claude's view stays coherent.
        if assistant_blocks:
            self.messages.append({"role": "assistant", "content": assistant_blocks})

        # If any pending confirmations: stop here and let the UI prompt.
        if result.pending_tools:
            return result

        # If any auto tools need to run, run them and loop back to Claude.
        if auto_calls_to_run:
            tool_result_blocks: list[dict[str, Any]] = []
            for call in auto_calls_to_run:
                tool_def = get_tool(call.tool_name)
                if tool_def is None:
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": call.tool_use_id,
                            "content": f"Unknown tool: {call.tool_name}",
                            "is_error": True,
                        }
                    )
                    continue
                try:
                    output = tool_def.function(**call.tool_input)
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": call.tool_use_id,
                            "content": output,
                        }
                    )
                    result.auto_tool_results.append(
                        {"tool": call.tool_name, "output": output}
                    )
                except Exception as e:  # noqa: BLE001
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": call.tool_use_id,
                            "content": f"Tool execution failed: {type(e).__name__}: {e}",
                            "is_error": True,
                        }
                    )

            self.messages.append({"role": "user", "content": tool_result_blocks})
            # Recurse: Claude will now see the tool results and keep going.
            recursed = self._model_turn()
            # Merge the recursive result into ours (flatten the chain).
            result.texts.extend(recursed.texts)
            result.pending_tools = recursed.pending_tools
            result.auto_tool_results.extend(recursed.auto_tool_results)
            result.end_turn = recursed.end_turn
            return result

        # No tools called. Claude is done with this turn.
        result.end_turn = response.stop_reason == "end_turn"
        return result

    def dump_conversation(self) -> str:
        """Export the full conversation as JSON for debugging."""
        return json.dumps(self.messages, indent=2, default=str)
