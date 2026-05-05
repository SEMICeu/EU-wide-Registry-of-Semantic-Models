import os
import sys
import json

import chainlit as cl

# Ensure project root is importable when loaded by `chainlit run graph_rag/main_chainlit.py`.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from graph_rag.api.service import chat_service


def _starting_prompt() -> str:
    uml_link = "https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/html/overview.jpg"
    return (
        "Welcome to the SEMIC Semantic Registry Assistant PoC.\n\n"
        "Ask me about models and metadata in the SEMIC Semantic Registry.\n\n"
        "How I retrieve information:\n"
        "- Graph traversal: precise, schema-based answers\n"
        "- Vector search: semantic matching over titles and descriptions\n"
        "- Hybrid: combines both when needed\n\n"
        "Tip: include class and relationship names from the UML for more precise answers.\n\n"
        f"UML diagram: {uml_link}"
    )


@cl.on_chat_start
async def on_chat_start() -> None:
    await cl.Message(content=_starting_prompt()).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    session_id = cl.user_session.get("sid")
    if not session_id:
        # Reuse Chainlit chat id for stable backend session memory.
        session_id = cl.user_session.get("id")
        cl.user_session.set("sid", session_id)

    final_answer = ""
    generated_cypher = ""
    query_results_preview = None
    async for event in chat_service.stream_chat(message.content, session_id=session_id):
        event_type = event.get("type")
        payload = event.get("payload", {})

        if event_type == "status":
            stage = payload.get("stage", "processing")
            await cl.Message(content=f"...{stage.replace('_', ' ')}").send()
        elif event_type == "routing":
            async with cl.Step(name="🧭 Routing", type="tool") as step:
                step.output = (
                    f"**Resolved question:** {payload.get('resolved_question', '')}\n"
                    f"**Follow-up detected:** `{payload.get('follow_up_detected', False)}`\n"
                    f"**Rewrite confidence:** `{payload.get('rewrite_confidence', 0.0):.2f}`\n\n"
                    f"**Intent:** `{payload.get('intent', '?')}`\n"
                    f"**Route:** `{payload.get('route', '?')}`\n"
                    f"**Reason:** {payload.get('plan', {}).get('reason', 'n/a')}"
                )
        elif event_type == "debug":
            if payload.get("cypher"):
                generated_cypher = str(payload["cypher"])
                async with cl.Step(name="🧠 Cypher", type="tool") as step:
                    step.output = f"```cypher\n{generated_cypher}\n```"
            if payload.get("context_preview") is not None:
                query_results_preview = payload.get("context_preview")
        elif event_type == "error":
            await cl.Message(content=f"An error occurred: `{payload.get('message', 'Unknown error')}`").send()
            return
        elif event_type == "final":
            final_answer = payload.get("answer", "")

    if generated_cypher:
        await cl.Message(
            content=f"Generated query:\n```cypher\n{generated_cypher}\n```"
        ).send()

    if query_results_preview is not None:
        pretty_results = json.dumps(query_results_preview, indent=2, ensure_ascii=False)
        await cl.Message(
            content=f"Query results:\n```json\n{pretty_results}\n```"
        ).send()

    if final_answer:
        await cl.Message(content=final_answer).send()

