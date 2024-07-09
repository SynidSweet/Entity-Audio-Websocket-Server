import os
import wave
import boto3
import audioop
import datetime
import logging
from config import Config

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self, audio_file_folder, bucket_name):
        self.audio_file_folder = audio_file_folder
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3')
        self.file_counter = 0
        self.last_non_silent_time = datetime.datetime.now()

        if not os.path.exists(self.audio_file_folder):
            os.makedirs(self.audio_file_folder)

    def process_audio(self, audio_chunk):
        rms = audioop.rms(audio_chunk, 2)
        logger.debug(f"RMS: {rms}, Threshold: {Config.SILENCE_THRESHOLD}")
        if rms >= Config.SILENCE_THRESHOLD:
            self.last_non_silent_time = datetime.datetime.now()
            return False  # Not silent
        return True  # Silent

    def is_inactive(self):
        time_since_last_non_silent = (datetime.datetime.now() - self.last_non_silent_time).total_seconds()
        logger.debug(f"Time since last non-silent: {time_since_last_non_silent}, Timeout: {Config.INACTIVITY_TIMEOUT}")
        return time_since_last_non_silent > Config.INACTIVITY_TIMEOUT

    def trim_silence(self, audio_buffer, sample_width, threshold):
        start_index = 0
        end_index = len(audio_buffer)

        for i in range(0, len(audio_buffer), sample_width):
            rms = audioop.rms(audio_buffer[i:i + sample_width], sample_width)
            if rms >= threshold:
                start_index = i
                break

        for i in range(len(audio_buffer) - sample_width, 0, -sample_width):
            rms = audioop.rms(audio_buffer[i:i + sample_width], sample_width)
            if rms >= threshold:
                end_index = i + sample_width
                break

        return audio_buffer[start_index:end_index]

    async def save_audio(self, audio_buffer, client_id):
        if not audio_buffer:
            return None

        audio_buffer = self.trim_silence(audio_buffer, 2, Config.SILENCE_THRESHOLD)

        if len(audio_buffer) == 0:
            logger.info(f"No non-silent audio detected for client: {client_id}")
            return None

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file_counter += 1
        audio_filename = f"audio_{client_id}_{timestamp}_{self.file_counter}.wav"
        
        audio_filepath = os.path.join(self.audio_file_folder, audio_filename)
        with wave.open(audio_filepath, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # Sample width in bytes
            wf.setframerate(44100)  # Frame rate
            wf.writeframes(audio_buffer)
        
        metadata = {
            'client_id': str(client_id),
            'timestamp': timestamp
        }
        self.s3_client.upload_file(
            audio_filepath, 
            self.bucket_name, 
            audio_filename,
            ExtraArgs={'Metadata': metadata}
        )
        os.remove(audio_filepath)  # Remove local file after upload

        return audio_filename

    async def stream_saved_audio(self, websocket, audio_filename):
        audio_filepath = os.path.join(self.audio_file_folder, audio_filename)

        self.s3_client.download_file(self.bucket_name, audio_filename, audio_filepath)
        
        with open(audio_filepath, 'rb') as f:
            data = f.read()
            await websocket.send(data)
        os.remove(audio_filepath)  # Remove local file after sending
        logger.info(f"Audio file sent to client and deleted locally: {audio_filepath}")