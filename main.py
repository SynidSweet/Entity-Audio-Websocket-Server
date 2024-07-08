import asyncio
import websockets
import logging
from config import Config
from websocket_handler import WebSocketHandler
from audio_processor import AudioProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketServer:
    def __init__(self):
        self.clients = {}
        self.audio_processor = AudioProcessor(Config.AUDIO_FILE_FOLDER, Config.BUCKET_NAME)

    async def handle_client(self, websocket, path):
        client_id = str(id(websocket))
        handler = WebSocketHandler(websocket, client_id, self.audio_processor)
        self.clients[client_id] = handler
        
        try:
            await handler.handle_connect()
            await handler.handle()
        finally:
            await handler.handle_disconnect()
            del self.clients[client_id]

    async def run(self):
        server = await websockets.serve(
            self.handle_client, 
            Config.SERVER_ADDRESS, 
            Config.SERVER_PORT
        )
        logger.info(f"Server started on {Config.SERVER_ADDRESS}:{Config.SERVER_PORT}")
        await server.wait_closed()

async def main():
    server = WebSocketServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())