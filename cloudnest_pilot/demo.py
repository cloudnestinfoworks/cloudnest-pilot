"""Demo mode for Cloudnest Pilot.

Lets people try the tool without an Anthropic API key.

Replaces the real Claude API client with a scripted responder that returns
realistic-looking output for the most common conversation flows. The user
sees the same UI, the same approval cards, the same tool-result rendering —
just powered by canned scripts instead of a real LLM.

This is critical for distribution. When someone sees Cloudnest Pilot on
Hacker News, they should be able to try it in 30 seconds without committing
to a billing setup.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .core import PendingToolCall, TurnResult


@dataclass
class DemoResponse:
    """A scripted response to a user message in demo mode."""

    matches: list[str]  # substrings that should be in the user message (case-insensitive)
    texts: list[str]
    tool_calls: list[PendingToolCall]


# Canned responses keyed by what's in the user's message.
# These are tuned to feel natural for the most common first-time user flows.
_RESPONSES: list[DemoResponse] = [
    # ORDER MATTERS — first match wins, so put more specific patterns first.

    # Specific: install-config.yaml (must check BEFORE generic "deploy")
    DemoResponse(
        matches=["install-config", "install config", "config file", "yaml"],
        texts=[
            (
                "Here's a sample `install-config.yaml` for an AWS IPI "
                "deployment:\n\n"
                "```yaml\n"
                "apiVersion: v1\n"
                "metadata:\n"
                "  name: meeru-test\n"
                "baseDomain: ocp.cloudnestinfoworks.com\n"
                "compute:\n"
                "- name: worker\n"
                "  replicas: 2\n"
                "  platform:\n"
                "    aws:\n"
                "      type: m5.large\n"
                "      zones:\n"
                "      - ap-south-1a\n"
                "      - ap-south-1b\n"
                "controlPlane:\n"
                "  name: master\n"
                "  replicas: 3\n"
                "  platform:\n"
                "    aws:\n"
                "      type: m5.xlarge\n"
                "      zones:\n"
                "      - ap-south-1a\n"
                "      - ap-south-1b\n"
                "      - ap-south-1c\n"
                "platform:\n"
                "  aws:\n"
                "    region: ap-south-1\n"
                "networking:\n"
                "  clusterNetwork:\n"
                "  - cidr: 10.128.0.0/14\n"
                "    hostPrefix: 23\n"
                "  serviceNetwork:\n"
                "  - 172.30.0.0/16\n"
                "  networkType: OVNKubernetes\n"
                "pullSecret: 'REPLACE_WITH_PULL_SECRET'\n"
                "sshKey: 'REPLACE_WITH_SSH_KEY'\n"
                "```\n\n"
                "**Things to customize:**\n"
                "- `pullSecret` — paste contents of `pull-secret.json`\n"
                "- `sshKey` — your `~/.ssh/id_rsa.pub`\n"
                "- `controlPlane.replicas` — 1 for dev, 3 for prod (HA)\n"
                "- `compute[0].replicas` — your desired worker count\n\n"
                "*[Demo mode: in real use, I'd save this to "
                "`~/.cloudnest-pilot/clusters/<name>/install-config.yaml` "
                "after your approval.]*"
            )
        ],
        tool_calls=[],
    ),
    # Specific: IAM permissions (check BEFORE generic deploy)
    DemoResponse(
        matches=["iam", "permission", "policy", "aws permissions"],
        texts=[
            (
                "Here's the AWS IAM policy needed for `openshift-install` to "
                "deploy on AWS:\n\n"
                "```json\n"
                "{\n"
                '  "Version": "2012-10-17",\n'
                '  "Statement": [\n'
                "    {\n"
                '      "Effect": "Allow",\n'
                '      "Action": [\n'
                '        "ec2:CreateVpc",\n'
                '        "ec2:CreateSubnet",\n'
                '        "ec2:CreateSecurityGroup",\n'
                '        "ec2:CreateInternetGateway",\n'
                '        "ec2:CreateNatGateway",\n'
                '        "ec2:CreateRouteTable",\n'
                '        "ec2:CreateTags",\n'
                '        "ec2:RunInstances",\n'
                '        "ec2:Describe*",\n'
                '        "iam:CreateRole",\n'
                '        "iam:CreatePolicy",\n'
                '        "iam:AttachRolePolicy",\n'
                '        "iam:PassRole",\n'
                '        "elasticloadbalancing:Create*",\n'
                '        "route53:ChangeResourceRecordSets",\n'
                '        "s3:CreateBucket",\n'
                '        "s3:PutObject"\n'
                "      ],\n"
                '      "Resource": "*"\n'
                "    }\n"
                "  ]\n"
                "}\n"
                "```\n\n"
                "**This is abbreviated** — the real policy needs about 100 "
                "permissions. In live mode, I'd save the complete policy to "
                "a file. Common approach: attach the AWS-managed "
                "`AdministratorAccess` for first install, then scope down.\n\n"
                "*[Demo mode: in real use, I'd write this to "
                "`~/.cloudnest-pilot/iam-policy.json` after your approval.]*"
            )
        ],
        tool_calls=[],
    ),
    # Specific: troubleshooting (check BEFORE generic deploy/install)
    DemoResponse(
        matches=["stuck", "fail", "error", "troubleshoot", "debug", "broken", "not working"],
        texts=[
            (
                "OpenShift install issues usually fall into a few categories. "
                "Tell me where you're stuck — but here are the common ones "
                "and how I diagnose them:\n\n"
                "**Stuck at bootstrap (`Waiting up to 30m0s for "
                "bootstrap-complete`):**\n"
                "- Bootstrap node failing to start → check AWS quotas, AMI "
                "availability\n"
                "- Bootstrap can't reach mirror → check network ACLs, route "
                "tables, NAT gateway\n"
                "- I'd ssh into bootstrap node and check "
                "`journalctl -u bootkube`\n\n"
                "**Stuck at cluster operators not Available:**\n"
                "- One specific operator hanging → `oc describe co <name>` "
                "and check the message field\n"
                "- Common: `image-registry` needs PVC, `monitoring` needs "
                "storage, `authentication` needs DNS\n\n"
                "**Stuck at LoadBalancer creation:**\n"
                "- AWS account limits → check service quotas\n"
                "- IAM permissions → re-run with `--log-level=debug`\n\n"
                "**Permission errors:**\n"
                "- IAM policy gaps — I can audit your policy and tell you "
                "what's missing\n"
                "- Wrong region — installer creates ELBs in a region you "
                "didn't expect\n\n"
                "Tell me your exact symptom (the error message or where it's "
                "stuck) and I'll narrow down the fix.\n\n"
                "*[Demo mode: in real use, I'd run diagnostic commands and "
                "interpret the output.]*"
            )
        ],
        tool_calls=[],
    ),
    # Specific: scaling (check BEFORE generic)
    DemoResponse(
        matches=["scale", "add worker", "more nodes", "add nodes"],
        texts=[
            (
                "To scale workers in an existing OpenShift cluster, you "
                "modify the MachineSet replica count. Here's the workflow:\n\n"
                "**1. List existing MachineSets:**\n"
                "```bash\n"
                "oc -n openshift-machine-api get machineset\n"
                "```\n\n"
                "Output looks like:\n"
                "```\n"
                "NAME                              DESIRED  CURRENT  READY  AGE\n"
                "meeru-test-worker-ap-south-1a     1        1        1      2h\n"
                "meeru-test-worker-ap-south-1b     1        1        1      2h\n"
                "```\n\n"
                "**2. Scale a specific MachineSet:**\n"
                "```bash\n"
                "oc -n openshift-machine-api scale machineset \\\n"
                "  meeru-test-worker-ap-south-1a --replicas=3\n"
                "```\n\n"
                "**3. Watch the new workers come up (3-5 min):**\n"
                "```bash\n"
                "watch oc get nodes\n"
                "```\n\n"
                "**Tips:**\n"
                "- Spread across multiple AZs for HA — scale each MachineSet "
                "evenly\n"
                "- For autoscaling, install ClusterAutoscaler operator + "
                "MachineAutoscaler resources\n"
                "- Worker upsizing (changing instance type) requires editing "
                "the MachineSet `providerSpec.value.instanceType`\n\n"
                "*[Demo mode: I can guide you through scaling, but won't "
                "actually run the commands without an API key.]*"
            )
        ],
        tool_calls=[],
    ),
    # Specific: cluster health (check BEFORE generic)
    DemoResponse(
        matches=["health", "status check", "diagnose cluster", "check cluster"],
        texts=[
            (
                "I'll check the health of your existing clusters by running "
                "`oc get` commands against each kubeconfig. Here's what I "
                "look at:\n\n"
                "1. **Node status** — `oc get nodes -o wide` checks for Ready "
                "state, capacity, and Kubernetes version drift\n"
                "2. **Cluster Operators** — `oc get co` flags any operator in "
                "Degraded, Progressing, or Unavailable state\n"
                "3. **Unhealthy pods** — `oc get pods --field-selector="
                "status.phase!=Running,status.phase!=Succeeded -A`\n"
                "4. **Cluster version** — `oc get clusterversion` for upgrade "
                "status\n"
                "5. **Recent events** — `oc get events --sort-by=.lastTimestamp"
                " -A | tail -20`\n\n"
                "*[Demo mode: I don't see any clusters in your "
                "`~/.cloudnest-pilot/clusters/` directory yet. In real use, "
                "I'd run these commands and summarize the results.]*"
            )
        ],
        tool_calls=[],
    ),
    # Generic: deployment (placed AFTER specific install/iam/troubleshoot)
    DemoResponse(
        matches=["deploy", "create cluster", "new cluster"],
        texts=[
            (
                "Great — let's deploy an OpenShift cluster on AWS!\n\n"
                "Here's what I'll need from you:\n\n"
                "1. **Cluster name** — short identifier (e.g., `dev-cluster`, "
                "`prod-east`)\n"
                "2. **Base domain** — DNS domain with a Route53 public hosted "
                "zone (e.g., `ocp.example.com`)\n"
                "3. **AWS region** — where to deploy (e.g., `us-east-1`, "
                "`ap-south-1`)\n"
                "4. **Worker count** — typically 2-3 for dev, 3+ for prod\n"
                "5. **Worker instance type** — `m5.large` for dev, "
                "`m5.xlarge` for prod\n"
                "6. **Pull secret path** — your Red Hat pull secret JSON\n\n"
                "Just tell me the values and I'll generate the install config "
                "and walk you through the deployment.\n\n"
                "*[Demo mode: in real use, I'd run AWS pre-flight checks "
                "before generating anything.]*"
            )
        ],
        tool_calls=[],
    ),
    # Generic: greeting/welcome (placed LAST so specific stuff matches first)
    DemoResponse(
        matches=["hello", "hi there", "hey", "what can you do", "what does this"],
        texts=[
            (
                "Hi! I'm **Cloudnest Pilot**, your AI assistant for OpenShift "
                "cluster operations. I run locally on your machine and use "
                "Claude AI to plan deployments and operations.\n\n"
                "**What I can help with:**\n\n"
                "- Deploy new OpenShift clusters on AWS (IPI method)\n"
                "- Generate `install-config.yaml` from your requirements\n"
                "- Generate AWS IAM policies for the installer\n"
                "- Validate AWS prerequisites (credentials, region, Route53)\n"
                "- Check the health of existing clusters\n"
                "- Troubleshoot deployment failures\n"
                "- Scale workers, perform upgrades\n\n"
                "**Important:** You're in **demo mode** right now. Tool calls "
                "won't actually run, but the UI is fully functional. To run "
                "real commands, set up an Anthropic API key and restart "
                "without `--demo`.\n\n"
                "What would you like to try?"
            ),
        ],
        tool_calls=[],
    ),
]

# Default fallback when no pattern matches.
_FALLBACK = DemoResponse(
    matches=[],
    texts=[
        (
            "*[Demo mode]*\n\n"
            "I'm running with canned responses since you don't have an "
            "Anthropic API key configured. I have scripted answers for these "
            "topics:\n\n"
            "- **\"deploy a cluster\"** → cluster deployment workflow\n"
            "- **\"IAM policy\"** → AWS IAM permissions for installer\n"
            "- **\"install-config.yaml\"** → sample config file\n"
            "- **\"check health\"** → cluster diagnostic commands\n"
            "- **\"troubleshoot stuck install\"** → debugging walkthrough\n"
            "- **\"scale workers\"** → MachineSet scaling\n\n"
            "Try one of those, or set up your Anthropic API key for "
            "unlimited real conversations:\n"
            "1. Get a key at https://console.anthropic.com/settings/keys\n"
            "2. Add it to `.env` as `ANTHROPIC_API_KEY=sk-ant-...`\n"
            "3. Restart without the `--demo` flag\n\n"
            "Typical Claude API cost: $3-5/month for active use."
        )
    ],
    tool_calls=[],
)


class DemoSession:
    """Drop-in replacement for AgentSession that uses canned responses.

    Same public API as AgentSession (send_user_message, dump_conversation),
    so the CLI and web UI work identically — they just see fake responses.
    """

    def __init__(self, config: object) -> None:
        self.config = config
        self.messages: list[dict] = []

    def send_user_message(self, text: str) -> TurnResult:
        """Match the user's message against canned responses."""
        # Simulate latency so it feels like a real API call
        time.sleep(0.5)

        self.messages.append({"role": "user", "content": text})

        text_lower = text.lower()

        # Find the first response whose patterns match
        chosen = _FALLBACK
        for response in _RESPONSES:
            for match in response.matches:
                if match.lower() in text_lower:
                    chosen = response
                    break
            if chosen is not _FALLBACK:
                break

        result = TurnResult()
        result.texts = list(chosen.texts)
        result.pending_tools = list(chosen.tool_calls)
        result.end_turn = len(chosen.tool_calls) == 0

        # Record assistant response
        self.messages.append(
            {
                "role": "assistant",
                "content": [{"type": "text", "text": t} for t in result.texts],
            }
        )

        return result

    def continue_after_confirmation(
        self,
        confirmed_calls: list[PendingToolCall],
        denied_calls: list[PendingToolCall],
    ) -> TurnResult:
        """Demo mode has no real tool calls, so this is a no-op."""
        result = TurnResult()
        result.texts = [
            "*[Demo mode: tool execution is disabled. In real mode, I'd run "
            "the command and show you the output.]*"
        ]
        result.end_turn = True
        return result

    def dump_conversation(self) -> str:
        import json

        return json.dumps(self.messages, indent=2, default=str)
