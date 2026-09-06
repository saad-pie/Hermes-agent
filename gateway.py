# gateway.py - Sub-Second Gemini Multimodal Live API Gateway
import asyncio
import os
import json
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

GEMINI_LIVE_WEBSOCKET_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"

@app.websocket("/ws/live")
async def live_multimodal_stream(websocket: WebSocket):
    """
    Establishes low-latency bidirectional WebSockets pipe between user browser/mobile
    and Gemini Multimodal Live API, bypassing GitHub Actions runner latency.
    """
    await websocket.accept()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        await websocket.close(code=4001, reason="GEMINI_API_KEY environment variable missing.")
        return

    target_url = f"{GEMINI_LIVE_WEBSOCKET_URL}?key={api_key}"

    async with websockets.connect(target_url) as gemini_ws:
        # Initial Handshake & Configuration Setup
        setup_msg = {
            "setup": {
                "model": "models/gemini-3.1-flash-live-preview",
                "generation_config": {"response_modalities": ["AUDIO", "TEXT"]}
            }
        }
        await gemini_ws.send(json.dumps(setup_msg))

        async def client_to_gemini():
            try:
                while True:
                    data = await websocket.receive_text()
                    await gemini_ws.send(data)
            except WebSocketDisconnect:
                pass

        async def gemini_to_client():
            try:
                async for message in gemini_ws:
                    await websocket.send_text(message)
            except Exception:
                pass

        # Pipe streams concurrently
        await asyncio.gather(client_to_gemini(), gemini_to_client())
      
