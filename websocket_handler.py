import asyncio
import websockets
import time
import logging
from config import Config
from ecs import start_ecs_task, stop_ecs_task

logger = logging.getLogger(__name__)

class WebSocketHandler:
    def __init__(self, websocket, client_id, audio_processor):
        self.websocket = websocket
        self.client_id = client_id
        self.audio_processor = audio_processor
        self.task_arn = None
        self.last_activity = asyncio.get_event_loop().time()
        self.audio_buffer = bytearray()
        self.silence_start = None
        self.recording_start = time.time()

    async def handle(self):
        self.task_arn = start_ecs_task(self.client_id)
        try:
            while True:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1)
                    self.last_activity = asyncio.get_event_loop().time()
                    await self.process_audio(message)
                except asyncio.TimeoutError:
                    if asyncio.get_event_loop().time() - self.last_activity > Config.INACTIVITY_TIMEOUT:
                        logger.info(f"Closing connection due to inactivity: {self.client_id}")
                        await self.websocket.close()
                        break
        except websockets.ConnectionClosed:
            logger.info(f"Connection closed: {self.client_id}")
        finally:
            await self.cleanup()

    async def process_audio(self, message):
        self.audio_buffer.extend(message)
        rms = audioop.rms(message, 2)

        if rms < Config.SILENCE_THRESHOLD:
            if self.silence_start is None:
                self.silence_start = time.time()
            elif time.time() - self.silence_start >= Config.SILENCE_DURATION / 1000:
                if self.recording_start < self.silence_start - 0.01:
                    await self.audio_processor.save_audio(bytes(self.audio_buffer), self.client_id)
                self.audio_buffer = bytearray()
                self.silence_start = None
                self.recording_start = time.time()
        else:
            self.silence_start = None

    async def cleanup(self):
        logger.info(f"Client disconnected: {self.client_id}")
        asyncio.create_task(self.delayed_ecs_task_termination())

    async def delayed_ecs_task_termination(self):
        await asyncio.sleep(Config.ECS_TASK_TERMINATION_DELAY)
        stop_ecs_task(self.task_arn)