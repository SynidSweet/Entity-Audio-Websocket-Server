import asyncio
import websockets

# WebSocket server address and port
SERVER_ADDRESS = "0.0.0.0"
SERVER_PORT = 8765

# Dictionary to keep track of active clients
clients = {}

async def handle_client(websocket, path):
    # Assign a unique identifier for each client
    client_id = id(websocket)
    clients[client_id] = websocket

    try:
        async for message in websocket:
            # Relay the audio data back to the same client
            await websocket.send(message)
    except websockets.ConnectionClosed:
        print(f"Connection closed: {path}")
    finally:
        # Remove the client from the active clients dictionary
        del clients[client_id]

async def main():
    async with websockets.serve(handle_client, SERVER_ADDRESS, SERVER_PORT):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
