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
        self.silence_start_time = None

        if not os.path.exists(self.audio_file_folder):
            os.makedirs(self.audio_file_folder)

    def process_audio(self, audio_chunk):
        rms = audioop.rms(audio_chunk, 2)
        logger.debug(f"Processing audio chunk, RMS: {rms}, Threshold: {Config.SILENCE_THRESHOLD}")

        if rms >= Config.SILENCE_THRESHOLD:
            self.last_non_silent_time = datetime.datetime.now()
            self.silence_start_time = None
            logger.debug("Audio chunk is not silent.")
            return False  # Not silent
        else:
            if self.silence_start_time is None:
                self.silence_start_time = datetime.datetime.now()
            elapsed_silence_time = (datetime.datetime.now() - self.silence_start_time).total_seconds() * 1000
            logger.debug(f"Elapsed silence time: {elapsed_silence_time} ms, Silence duration: {Config.SILENCE_DURATION} ms")
            if elapsed_silence_time >= Config.SILENCE_DURATION:
                logger.debug("Detected silence.")
                self.reset_silence_timer()
                return True  # Silent
            return False  # Not silent yet

    def reset_silence_timer(self):
        self.silence_start_time = None

    def is_inactive(self):
        time_since_last_non_silent = (datetime.datetime.now() - self.last_non_silent_time).total_seconds()
        logger.debug(f"Time since last non-silent: {time_since_last_non_silent}, Inactivity timeout: {Config.INACTIVITY_TIMEOUT}")
        return time_since_last_non_silent > Config.INACTIVITY_TIMEOUT

    def is_buffer_silent(self, audio_buffer):
        rms = audioop.rms(audio_buffer, 2)
        logger.debug(f"Buffer RMS: {rms}, Threshold: {Config.SILENCE_THRESHOLD}")
        return rms < Config.SILENCE_THRESHOLD

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

        trimmed_buffer = audio_buffer[start_index:end_index]
        logger.debug(f"Trimmed audio buffer from {start_index} to {end_index}")
        return trimmed_buffer

    async def save_audio(self, audio_buffer, client_id):
        if not audio_buffer:
            logger.debug("Audio buffer is empty, nothing to save.")
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
            wf.setsampwidth(2)  # Sample width in bytes (16 bits = 2 bytes)
            wf.setframerate(44100)  # Frame rate set to 44100 Hz
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

        logger.info(f"Saved audio file {audio_filename} for client {client_id}")
        return audio_filename

    async def stream_saved_audio(self, websocket, audio_filename):
        audio_filepath = os.path.join(self.audio_file_folder, audio_filename)

        self.s3_client.download_file(self.bucket_name, audio_filename, audio_filepath)

        with open(audio_filepath, 'rb') as f:
            data = f.read()
            await websocket.send(data)
        os.remove(audio_filepath)  # Remove local file after sending
        logger.info(f"Audio file sent to client and deleted locally: {audio_filepath}")
