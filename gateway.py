import asyncio
import json
import os
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import websockets

app = FastAPI()

# Standard Gemini Multimodal Live API WebSocket Endpoint
GEMINI_LIVE_WEBSOCKET_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"
GITHUB_DISPATCH_URL = f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY', 'your-repo/hermes')}/dispatches"

# Define the Tool Schema for Gemini Live
HERMES_TOOL_DECLARATION = {
    "function_declarations": [
        {
            "name": "trigger_hermes_agent",
            "description": "Trigger this ONLY when the user asks to perform an action, run code, execute shell scripts, browse the web, or modify files.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "task_description": {
                        "type": "STRING",
                        "description": "The exact objective or instructions for the background agent to execute."
                    },
                    "target_layer": {
                        "type": "STRING",
                        "description": "Optional layer to execute: 'claude' (GUI/browser), 'chatgpt' (research/docs), 'background' (CLI/code)."
                    }
                },
                "required": ["task_description"]
            }
        }
    ]
}

async def dispatch_github_workflow(task_description: str, target_layer: str = "background"):
    """Asynchronously dispatches a background task to your GitHub Actions / Hermes engine."""
    gh_token = os.getenv("GITHUB_TOKEN")
    if not gh_token:
        print("[Hermes Dispatcher] Warning: GITHUB_TOKEN not set. Skipping workflow dispatch.")
        return False

    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "event_type": "hermes_request",
        "client_payload": {
            "question": task_description,
            "target_layer": target_layer
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GITHUB_DISPATCH_URL, headers=headers, json=payload, timeout=5.0)
            return response.status_code == 204
        except Exception as e:
            print(f"[Hermes Dispatcher] Error triggering workflow: {e}")
            return False

@app.websocket("/ws/live")
async def live_multimodal_stream(websocket: WebSocket):
    await websocket.accept()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        await websocket.close(
            code=4001, reason="GEMINI_API_KEY environment variable missing."
        )
        return

    target_url = f"{GEMINI_LIVE_WEBSOCKET_URL}?key={api_key}"

    try:
        async with websockets.connect(target_url) as gemini_ws:
            # 1. Setup Handshake with Audio Modality + Hermes Agent Tool attached
            setup_msg = {
                "setup": {
                    "model": "models/gemini-3.1-flash-live-preview",
                    "generationConfig": {
                        "responseModalities": ["AUDIO", "TEXT"]
                    },
                    "tools": [HERMES_TOOL_DECLARATION]
                }
            }
            await gemini_ws.send(json.dumps(setup_msg))

            # 2. Receive setup complete acknowledgement
            setup_ack = await gemini_ws.recv()
            await websocket.send_text(setup_ack)

            async def client_to_gemini():
                """Forwards audio/text chunks from Client to Gemini Live API"""
                try:
                    while True:
                        message = await websocket.receive()
                        if "text" in message:
                            await gemini_ws.send(message["text"])
                        elif "bytes" in message:
                            await gemini_ws.send(message["bytes"])
                except WebSocketDisconnect:
                    pass

            async def gemini_to_client():
                """Forwards responses from Gemini to Client, intercepting toolCalls"""
                try:
                    async for message in gemini_ws:
                        # Forward raw binary audio frames straight to the client
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                            continue

                        # Parse JSON server frames
                        data = json.loads(message)

                        # Intercept Asynchronous Tool Call Events from Gemini
                        if "toolCall" in data:
                            tool_call = data["toolCall"]
                            function_calls = tool_call.get("functionCalls", [])

                            for fc in function_calls:
                                call_id = fc.get("id")
                                name = fc.get("name")
                                args = fc.get("args", {})

                                if name == "trigger_hermes_agent":
                                    task_desc = args.get("task_description", "")
                                    layer = args.get("target_layer", "background")
                                    
                                    # Trigger GitHub Action in non-blocking background task
                                    asyncio.create_task(dispatch_github_workflow(task_desc, layer))

                                    # Send immediate toolResponse frame back to Gemini Live
                                    tool_response_msg = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "id": call_id,
                                                    "response": {
                                                        "output": {
                                                            "status": "Task dispatched successfully to Hermes AI Agent worker in background."
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_response_msg))

                        # Forward standard text transcripts / server content to client UI
                        await websocket.send_text(message)

                except Exception as e:
                    print(f"[Gateway Error] {e}")

            # 3. Pipe bidirectional streams concurrently
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_gemini()),
                    asyncio.create_task(gemini_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

    except Exception as e:
        await websocket.close(code=1011, reason=str(e))
