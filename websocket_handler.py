import json
import boto3
import time
import logging
from botocore.exceptions import ClientError
import websockets
from audio_processor import AudioProcessor
from config import Config

logger = logging.getLogger(__name__)

dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')
table = dynamodb.Table('entity-user-session-table')

class WebSocketHandler:
    def __init__(self, websocket, client_id, audio_processor: AudioProcessor):
        self.websocket = websocket
        self.client_id = client_id
        self.audio_processor = audio_processor
        self.audio_buffer = bytearray()

    async def handle_connect(self):
        logger.info(f"New client connected: {self.client_id}")
        try:
            table.put_item(
                Item={
                    'user_id': self.client_id,
                    'connection_id': str(id(self.websocket)),
                    'last_active': int(time.time())
                }
            )
        except ClientError as e:
            logger.error(f"Error updating DynamoDB on connect: {e}")

    async def handle_disconnect(self):
        logger.info(f"Client disconnected: {self.client_id}")
        try:
            table.delete_item(Key={'user_id': self.client_id})
        except ClientError as e:
            logger.error(f"Error updating DynamoDB on disconnect: {e}")

    async def handle(self):
        try:
            async for message in self.websocket:
                await self.process_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed for client: {self.client_id}")

    async def process_message(self, message):
        if isinstance(message, bytes):
            # Treat the message as audio data
            await self.handle_audio(message)
        elif isinstance(message, str):
            # Treat the message as a JSON string
            try:
                data = json.loads(message)
                if data['type'] == 'audio':
                    await self.handle_audio(data['audio'])
                elif data['type'] == 'command':
                    await self.handle_command(data['command'])
                else:
                    logger.warning(f"Unknown message type: {data['type']}")
            except json.JSONDecodeError:
                logger.error("Received invalid JSON")
            except UnicodeDecodeError:
                logger.error("Received message with invalid UTF-8 encoding")
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
        else:
            logger.error("Received message of unknown type")

    async def handle_audio(self, audio_data):

        is_silent = self.audio_processor.process_audio(audio_data)
        if is_silent:
            if len(self.audio_buffer) > 0:
                audio_filename = await self.audio_processor.save_audio(bytes(self.audio_buffer), self.client_id)
                self.audio_buffer = bytearray()
                logger.info(f"Audio saved: {audio_filename}")
            return

        self.audio_buffer.extend(audio_data)

    async def handle_command(self, command):
        if command == 'start_recording':
            self.audio_buffer = bytearray()
            await self.websocket.send(json.dumps({'status': 'recording_started'}))
        elif command == 'stop_recording':
            if len(self.audio_buffer) > 0:
                audio_filename = await self.audio_processor.save_audio(bytes(self.audio_buffer), self.client_id)
                self.audio_buffer = bytearray()
                await self.websocket.send(json.dumps({'status': 'recording_saved', 'filename': audio_filename}))
            else:
                await self.websocket.send(json.dumps({'status': 'no_audio_recorded'}))
        elif command.startswith('play_'):
            audio_filename = command.split('_', 1)[1]
            await self.stream_audio(audio_filename)
        else:
            logger.warning(f"Unknown command: {command}")

    async def stream_audio(self, audio_filename):
        try:
            audio_data = await self.audio_processor.get_audio(audio_filename)
            await self.websocket.send(json.dumps({'type': 'audio_stream_start', 'filename': audio_filename}))
            await self.websocket.send(audio_data)
            await self.websocket.send(json.dumps({'type': 'audio_stream_end'}))
        except Exception as e:
            logger.error(f"Error streaming audio: {e}")
            await self.websocket.send(json.dumps({'type': 'error', 'message': 'Error streaming audio'}))
