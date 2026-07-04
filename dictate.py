#!/usr/bin/env python3
import os
import signal
import subprocess
import asyncio
import wave
from wyoming.client import AsyncTcpClient
from wyoming.audio import AudioStart, AudioChunk, AudioStop
from wyoming.asr import Transcribe, Transcript

PID_FILE = "/tmp/dictate_recording.pid"
WAV_FILE = "/tmp/dictate.wav"

async def transcribe_audio():
    try:
        client = AsyncTcpClient('127.0.0.1', 10300)
        await client.connect()
        
        # Request transcription (using the default auto language/medium-int8 model)
        await client.write_event(Transcribe().event())
        
        # Send Audio
        with wave.open(WAV_FILE, 'rb') as wav:
            rate = wav.getframerate()
            width = wav.getsampwidth()
            channels = wav.getnchannels()
            
            await client.write_event(AudioStart(rate=rate, width=width, channels=channels).event())
            
            while True:
                chunk = wav.readframes(4096)
                if not chunk:
                    break
                await client.write_event(AudioChunk(rate=rate, width=width, channels=channels, audio=chunk).event())
                
            await client.write_event(AudioStop().event())
        
        # Wait for transcription result
        while True:
            event = await client.read_event()
            if event is None:
                break
            if Transcript.is_type(event.type):
                transcript = Transcript.from_event(event)
                return transcript.text
    except Exception as e:
        print(f"Transcription error: {e}")
    return ""

def start_recording():
    # Start pw-record in the background
    print("Starting recording...")
    subprocess.run(["notify-send", "-t", "2000", "🎙️ Dictation", "Started listening..."])
    # 16kHz, 16-bit, mono is ideal for Whisper
    proc = subprocess.Popen(["pw-record", "--channels=1", "--rate=16000", "--format=s16", WAV_FILE])
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))
    # Optional: You could play a tiny sound here to notify you it started
    print("Recording started. Trigger again to stop and transcribe.")

def stop_recording_and_type():
    print("Stopping recording...")
    with open(PID_FILE, "r") as f:
        pid = int(f.read().strip())
    
    os.remove(PID_FILE)
    
    try:
        os.kill(pid, signal.SIGINT)
        # Wait a moment for the WAV file header to be finalized by pw-record
        import time
        time.sleep(0.5)
    except ProcessLookupError:
        pass
    
    print("Sending to Whisper...")
    subprocess.run(["notify-send", "-t", "2000", "⚙️ Dictation", "Sending to Whisper..."])
    text = asyncio.run(transcribe_audio())
    text = text.strip()
    
    if text:
        print(f"Transcribed: {text}")
        # Append a space so next sentence doesn't stick
        safe_text = (text + " ").replace('"', '\\"')
        subprocess.run(f'wtype "{safe_text}"', shell=True)
    else:
        print("No speech detected.")

if __name__ == "__main__":
    if os.path.exists(PID_FILE):
        stop_recording_and_type()
    else:
        start_recording()
