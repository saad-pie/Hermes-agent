import asyncio
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import websockets

app = FastAPI()

# Standard Gemini Multimodal Live API WebSocket Endpoint
GEMINI_LIVE_WEBSOCKET_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"


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
      # Target model string for Gemini 3 Flash Live
      setup_msg = {
          "setup": {
              "model": "models/gemini-3.1-flash-live-preview",
              "generationConfig": {
                  "responseModalities": ["AUDIO", "TEXT"]
              },
          }
      }
      await gemini_ws.send(json.dumps(setup_msg))

      # Await connection acknowledgement from Gemini Live server
      setup_ack = await gemini_ws.recv()
      await websocket.send_text(setup_ack)

      async def client_to_gemini():
        try:
          while True:
            # Handle text JSON frames or binary PCM audio streams
            message = await websocket.receive()
            if "text" in message:
              await gemini_ws.send(message["text"])
            elif "bytes" in message:
              await gemini_ws.send(message["bytes"])
        except WebSocketDisconnect:
          pass

      async def gemini_to_client():
        try:
          async for message in gemini_ws:
            if isinstance(message, bytes):
              await websocket.send_bytes(message)
            else:
              await websocket.send_text(message)
        except Exception:
          pass

      # Run concurrently and cancel remaining task on disconnect
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
