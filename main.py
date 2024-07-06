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
        client_id = id(websocket)
        handler = WebSocketHandler(websocket, client_id, self.audio_processor)
        self.clients[client_id] = handler
        logger.info(f"New client connected: {client_id}, Path: {path}")
        logger.info(f"Total connected clients: {len(self.clients)}")
        await handler.handle()
        del self.clients[client_id]

    async def check_inactive_connections(self):
        while True:
            await asyncio.sleep(60)  # Check every minute
            current_time = asyncio.get_event_loop().time()
            for client_id, handler in list(self.clients.items()):
                if current_time - handler.last_activity > Config.INACTIVITY_TIMEOUT:
                    logger.info(f"Closing inactive connection: {client_id}")
                    await handler.websocket.close()

    async def run(self):
        logger.info(f"Starting server at {Config.SERVER_ADDRESS}:{Config.SERVER_PORT}")
        server = await websockets.serve(self.handle_client, Config.SERVER_ADDRESS, Config.SERVER_PORT)
        
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.check_inactive_connections())
            tg.create_task(server.wait_closed())
        
        logger.info("Server started. Waiting for clients to connect...")

async def main():
    server = WebSocketServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())