class Config:
    # Existing settings
    SERVER_ADDRESS = "0.0.0.0"
    SERVER_PORT = 8765
    SILENCE_THRESHOLD = 500
    SILENCE_DURATION = 400  # milliseconds
    AUDIO_FILE_FOLDER = "audio_files"
    BUCKET_NAME = 'entity-installation-audio-storage'
    INACTIVITY_TIMEOUT = 300  # 5 minutes
    ECS_TASK_TERMINATION_DELAY = 300  # 5 minutes

    # New ECS settings
    ECS_CLUSTER_NAME = 'your-cluster-name'
    ECS_TASK_DEFINITION = 'your-task-definition'
    ECS_CONTAINER_NAME = 'your-container-name'
    ECS_SUBNET_ID = 'your-subnet-id'
    ECS_LAUNCH_TYPE = 'FARGATE'