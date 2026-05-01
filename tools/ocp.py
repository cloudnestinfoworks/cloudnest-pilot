"""OCP-specific tools.

These are built on top of read_file + shell, but give Claude cleaner
semantics for common operations.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .registry import tool

# Set by core.py at startup from config.
_CLUSTERS_DIR: Path | None = None


def set_clusters_dir(path: Path) -> None:
    global _CLUSTERS_DIR
    _CLUSTERS_DIR = path


@tool(
    name="list_clusters",
    description=(
        "List OpenShift clusters that this tool has installed. Each "
        "cluster has its own subdirectory under the clusters dir "
        "containing install-config.yaml, auth/kubeconfig, and logs. "
        "Returns a list of cluster names and their installation status."
    ),
    input_schema={
        "type": "object",
        "properties": {},
    },
    requires_confirmation=False,
)
def list_clusters() -> str:
    if _CLUSTERS_DIR is None or not _CLUSTERS_DIR.exists():
        return "No clusters directory configured yet."
    entries: list[str] = []
    for child in sorted(_CLUSTERS_DIR.iterdir()):
        if not child.is_dir():
            continue
        kubeconfig = child / "auth" / "kubeconfig"
        metadata = child / "metadata.json"
        status = "configured"
        if metadata.exists():
            status = "installed"
        if kubeconfig.exists():
            status = "installed (kubeconfig present)"
        entries.append(f"  • {child.name}: {status} — {child}")
    if not entries:
        return f"No clusters found under {_CLUSTERS_DIR}"
    return f"Clusters in {_CLUSTERS_DIR}:\n" + "\n".join(entries)


@tool(
    name="get_cluster_status",
    description=(
        "Get the health and status of an installed OpenShift cluster. "
        "Runs a series of `oc` commands against the cluster using the "
        "kubeconfig from its installation directory. Returns node status, "
        "cluster operators, and a summary of pod health. Read-only."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "cluster_name": {
                "type": "string",
                "description": "Name of a cluster returned by list_clusters.",
            },
        },
        "required": ["cluster_name"],
    },
    requires_confirmation=False,
)
def get_cluster_status(cluster_name: str) -> str:
    if _CLUSTERS_DIR is None:
        return "Clusters directory not configured."
    cluster_dir = _CLUSTERS_DIR / cluster_name
    kubeconfig = cluster_dir / "auth" / "kubeconfig"
    if not kubeconfig.exists():
        return (
            f"No kubeconfig found for cluster '{cluster_name}' at {kubeconfig}. "
            "Either the cluster was not installed by this tool or the install "
            "is incomplete."
        )

    env = {"KUBECONFIG": str(kubeconfig)}

    def _run(argv: list[str]) -> str:
        try:
            r = subprocess.run(
                argv,
                env={**env, "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"},
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            return r.stdout.strip() or r.stderr.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return f"TIMEOUT running: {' '.join(argv)}"
        except FileNotFoundError:
            return f"`{argv[0]}` not on PATH"

    sections = []

    # Nodes
    sections.append("=== Nodes ===")
    sections.append(_run(["oc", "get", "nodes", "-o", "wide"]))

    # Cluster operators
    sections.append("\n=== Cluster Operators ===")
    sections.append(_run(["oc", "get", "clusteroperators"]))

    # Any pods not Running/Completed
    sections.append("\n=== Unhealthy pods across all namespaces ===")
    sections.append(
        _run(
            [
                "oc",
                "get",
                "pods",
                "--all-namespaces",
                "--field-selector=status.phase!=Running,status.phase!=Succeeded",
                "-o",
                "wide",
            ]
        )
    )

    # Cluster version
    sections.append("\n=== Cluster Version ===")
    sections.append(_run(["oc", "get", "clusterversion"]))

    return "\n".join(sections)
