class Config:
    # Existing settings
    SERVER_ADDRESS = "0.0.0.0"
    SERVER_PORT = 8765
    SILENCE_THRESHOLD = 500
    SILENCE_DURATION = 400  # milliseconds
    AUDIO_FILE_FOLDER = "audio_files"
    BUCKET_NAME = 'entity-installation-audio-storage'
    INACTIVITY_TIMEOUT = 300  # 5 minutes