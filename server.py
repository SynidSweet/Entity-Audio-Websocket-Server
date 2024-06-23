import asyncio
import datetime
import wave
import websockets
import audioop
import os

# WebSocket server address and port
SERVER_ADDRESS = "0.0.0.0"
SERVER_PORT = 8765

# Silence threshold and duration (in milliseconds)
SILENCE_THRESHOLD = 500  # Adjust this value based on your environment
SILENCE_DURATION = 400  # Duration to detect silence, milliseconds

audio_file_folder = "audio_files"

# Ensure the audio_files directory exists
if not os.path.exists(audio_file_folder):
    os.makedirs(audio_file_folder)

# Counter to ensure unique file names
file_counter = 0

# Dictionary to keep track of active clients
clients = {}

def trim_silence(audio_buffer, sample_width, threshold):
    """Remove silence from the beginning and end of the audio buffer."""
    start_index = 0
    end_index = len(audio_buffer)

    # Detect the start of non-silent audio
    for i in range(0, len(audio_buffer), sample_width):
        rms = audioop.rms(audio_buffer[i:i + sample_width], sample_width)
        if rms >= threshold:
            start_index = i
            break

    # Detect the end of non-silent audio
    for i in range(len(audio_buffer) - sample_width, 0, -sample_width):
        rms = audioop.rms(audio_buffer[i:i + sample_width], sample_width)
        if rms >= threshold:
            end_index = i + sample_width
            break

    return audio_buffer[start_index:end_index]

async def save_audio(audio_buffer, client_id):
    global file_counter
    if audio_buffer:
        # Trim silence from the beginning and end
        audio_buffer = trim_silence(audio_buffer, 2, SILENCE_THRESHOLD)

        if len(audio_buffer) == 0:
            print(f"No non-silent audio detected for client: {client_id}")
            return None

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_counter += 1
        audio_filename = f"audio_{client_id}_{timestamp}_{file_counter}.wav"
        audio_filepath = os.path.join(audio_file_folder, audio_filename)
        with wave.open(audio_filepath, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # Sample width in bytes
            wf.setframerate(44100)  # Frame rate
            wf.writeframes(audio_buffer)
        print(f"Audio saved to file: {audio_filepath}")
        return audio_filepath
    return None

async def stream_saved_audio(websocket, audio_filepath):
    with open(audio_filepath, 'rb') as f:
        data = f.read()
        await websocket.send(data)
    os.remove(audio_filepath)
    print(f"Audio file sent to client and deleted: {audio_filepath}")

async def handle_client(websocket, path):
    client_id = id(websocket)
    clients[client_id] = websocket
    print(f"New client connected: {client_id}, Path: {path}")
    print(f"Total connected clients: {len(clients)}")

    audio_buffer = bytearray()
    silence_start = None
    recording_start = datetime.datetime.now()

    try:
        async for message in websocket:
            audio_buffer.extend(message)
            rms = audioop.rms(message, 2)

            if rms < SILENCE_THRESHOLD:
                elapsed_time = (datetime.datetime.now() - silence_start).total_seconds() * 1000 if silence_start else 0

                if silence_start is None:
                    silence_start = datetime.datetime.now()

                elif elapsed_time >= SILENCE_DURATION:

                    if recording_start < silence_start - datetime.timedelta(milliseconds=10):
                        audio_filepath = await save_audio(bytes(audio_buffer), client_id)
                        if audio_filepath:
                            await stream_saved_audio(websocket, audio_filepath)

                    audio_buffer = bytearray()
                    silence_start = None
                    recording_start = datetime.datetime.now()

            else:
                silence_start = None
    except websockets.ConnectionClosed:
        print(f"Connection closed: {client_id}, Path: {path}")
    finally:
        del clients[client_id]
        print(f"Client disconnected: {client_id}")
        print(f"Total connected clients: {len(clients)}")

async def main():
    print(f"Starting server at {SERVER_ADDRESS}:{SERVER_PORT}")
    async with websockets.serve(handle_client, SERVER_ADDRESS, SERVER_PORT):
        print("Server started. Waiting for clients to connect...")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
