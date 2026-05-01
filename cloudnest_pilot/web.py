"""Flask web server for the OCP agent.

Endpoints:
  GET  /                      -> chat UI
  POST /api/chat/message      -> send user message, get response + pending tools
  POST /api/chat/confirm      -> user's y/n decisions on pending tools
  GET  /api/clusters          -> cluster status sidebar data

Session is kept in-memory keyed by a session cookie. Since this is a local
tool for a single user, we don't need auth or persistence.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, session

from .config import Config
from .core import AgentSession, PendingToolCall


def create_app(config: Config) -> Flask:
    template_folder = Path(__file__).resolve().parent / "web" / "templates"
    static_folder = Path(__file__).resolve().parent / "web" / "static"

    app = Flask(
        __name__,
        template_folder=str(template_folder),
        static_folder=str(static_folder),
    )
    app.secret_key = uuid.uuid4().hex  # session cookies, regenerated each launch

    # In-memory session store. Single user local tool.
    sessions: dict[str, AgentSession] = {}
    pending_by_session: dict[str, list[PendingToolCall]] = {}

    def _get_session() -> AgentSession:
        sid = session.get("sid")
        if not sid or sid not in sessions:
            sid = uuid.uuid4().hex
            session["sid"] = sid
            sessions[sid] = AgentSession(config)
            pending_by_session[sid] = []
        return sessions[sid]

    @app.route("/")
    def index() -> str:
        _get_session()  # ensure cookie set
        return render_template("chat.html")

    @app.route("/api/chat/message", methods=["POST"])
    def chat_message() -> Any:
        data = request.get_json(force=True)
        text = (data or {}).get("text", "").strip()
        if not text:
            return jsonify({"error": "empty message"}), 400

        agent = _get_session()
        sid = session["sid"]
        try:
            turn = agent.send_user_message(text)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": f"Claude API error: {e}"}), 500

        pending_by_session[sid] = list(turn.pending_tools)
        return jsonify(
            {
                "texts": turn.texts,
                "auto_tool_results": turn.auto_tool_results,
                "pending_tools": [
                    {
                        "tool_use_id": p.tool_use_id,
                        "tool_name": p.tool_name,
                        "tool_input": p.tool_input,
                    }
                    for p in turn.pending_tools
                ],
                "end_turn": turn.end_turn,
            }
        )

    @app.route("/api/chat/confirm", methods=["POST"])
    def chat_confirm() -> Any:
        data = request.get_json(force=True) or {}
        approvals: dict[str, bool] = data.get("approvals", {})
        edited_inputs: dict[str, dict[str, Any]] = data.get("edited_inputs", {})

        agent = _get_session()
        sid = session["sid"]
        pending = pending_by_session.get(sid, [])

        confirmed: list[PendingToolCall] = []
        denied: list[PendingToolCall] = []
        for call in pending:
            # Apply any user edits to the tool input.
            if call.tool_use_id in edited_inputs:
                call.tool_input = {**call.tool_input, **edited_inputs[call.tool_use_id]}
            if approvals.get(call.tool_use_id, False):
                confirmed.append(call)
            else:
                denied.append(call)

        pending_by_session[sid] = []

        try:
            turn = agent.continue_after_confirmation(confirmed, denied)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": f"Tool execution error: {e}"}), 500

        pending_by_session[sid] = list(turn.pending_tools)
        return jsonify(
            {
                "texts": turn.texts,
                "auto_tool_results": turn.auto_tool_results,
                "pending_tools": [
                    {
                        "tool_use_id": p.tool_use_id,
                        "tool_name": p.tool_name,
                        "tool_input": p.tool_input,
                    }
                    for p in turn.pending_tools
                ],
                "end_turn": turn.end_turn,
            }
        )

    @app.route("/api/clusters", methods=["GET"])
    def list_clusters_api() -> Any:
        """Sidebar data: list clusters and their basic state."""
        clusters = []
        for child in sorted(config.clusters_dir.iterdir()) if config.clusters_dir.exists() else []:
            if not child.is_dir():
                continue
            kubeconfig = child / "auth" / "kubeconfig"
            metadata = child / "metadata.json"
            status = "configured"
            if metadata.exists():
                status = "installed"
            if kubeconfig.exists():
                status = "ready"
            clusters.append(
                {
                    "name": child.name,
                    "status": status,
                    "path": str(child),
                }
            )
        return jsonify({"clusters": clusters})

    @app.route("/api/reset", methods=["POST"])
    def reset_session() -> Any:
        sid = session.get("sid")
        if sid in sessions:
            del sessions[sid]
        if sid in pending_by_session:
            del pending_by_session[sid]
        session.clear()
        return jsonify({"ok": True})

    return app


def run_web(config: Config) -> None:
    app = create_app(config)
    print(f"\n  Cloudnest Pilot web UI → http://localhost:{config.web_port}\n")
    print(f"  (Press Ctrl+C to stop)\n")
    app.run(host="127.0.0.1", port=config.web_port, debug=False)

def run_web_demo(port: int = 8765) -> None:
    """Web UI in demo mode — uses DemoSession instead of real Claude API."""
    from .demo import DemoSession
    
    template_folder = Path(__file__).resolve().parent / "web" / "templates"
    static_folder = Path(__file__).resolve().parent / "web" / "static"
    
    app = Flask(
        __name__,
        template_folder=str(template_folder),
        static_folder=str(static_folder),
    )
    app.secret_key = uuid.uuid4().hex
    
    # Single in-memory demo session shared across the user's browser tabs
    demo_session = DemoSession(config=None)
    pending_tools: list = []
    
    @app.route("/")
    def index() -> str:
        return render_template("chat.html")
    
    @app.route("/api/chat/message", methods=["POST"])
    def chat_message():
        data = request.get_json(force=True)
        text = (data or {}).get("text", "").strip()
        if not text:
            return jsonify({"error": "empty message"}), 400
        
        try:
            turn = demo_session.send_user_message(text)
        except Exception as e:
            return jsonify({"error": f"Demo error: {e}"}), 500
        
        return jsonify({
            "texts": turn.texts,
            "auto_tool_results": [],
            "pending_tools": [],
            "end_turn": turn.end_turn,
        })
    
    @app.route("/api/chat/confirm", methods=["POST"])
    def chat_confirm():
        # Demo mode never has tool calls to confirm
        return jsonify({
            "texts": ["*[Demo mode: no tool execution.]*"],
            "auto_tool_results": [],
            "pending_tools": [],
            "end_turn": True,
        })
    
    @app.route("/api/clusters", methods=["GET"])
    def list_clusters_api():
        return jsonify({"clusters": []})
    
    @app.route("/api/reset", methods=["POST"])
    def reset_session():
        nonlocal demo_session
        demo_session = DemoSession(config=None)
        return jsonify({"ok": True})
    
    print(f"\n  Cloudnest Pilot DEMO web UI → http://localhost:{port}\n")
    print(f"  (Press Ctrl+C to stop)\n")
    app.run(host="127.0.0.1", port=port, debug=False)