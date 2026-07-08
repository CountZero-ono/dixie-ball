import asyncio
import logging
import subprocess
import argparse
from typing import Optional

from wyoming.server import AsyncServer, AsyncEventHandler
from wyoming.client import AsyncTcpClient
from wyoming.audio import AudioStart, AudioChunk, AudioStop
from wyoming.asr import Transcript
from wyoming.event import Event

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_LOGGER = logging.getLogger("dixie_dictate")

class DictationHandler(AsyncEventHandler):
    def __init__(self, cli_args, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cli_args = cli_args
        self.whisper_client: Optional[AsyncTcpClient] = None
        self.whisper_task: Optional[asyncio.Task] = None
        self.client_id = id(self)
        _LOGGER.info(f"[{self.client_id}] New connection from device")

    async def handle_event(self, event: Event) -> bool:
        if AudioStart.is_type(event.type):
            _LOGGER.info(f"[{self.client_id}] Dictation started, connecting to Whisper at {self.cli_args.whisper_host}:{self.cli_args.whisper_port}")
            self.whisper_client = AsyncTcpClient(self.cli_args.whisper_host, self.cli_args.whisper_port)
            await self.whisper_client.connect()
            await self.whisper_client.write_event(event)
            self.whisper_task = asyncio.create_task(self._read_from_whisper())
        elif AudioChunk.is_type(event.type):
            if self.whisper_client:
                await self.whisper_client.write_event(event)
        elif AudioStop.is_type(event.type):
            _LOGGER.info(f"[{self.client_id}] Audio recording stopped. Waiting for transcript...")
            if self.whisper_client:
                await self.whisper_client.write_event(event)
        else:
            _LOGGER.debug(f"[{self.client_id}] Ignored event: {event.type}")
        return True

    async def _read_from_whisper(self):
        try:
            while True:
                event = await self.whisper_client.read_event()
                if event is None:
                    break
                
                if Transcript.is_type(event.type):
                    transcript = Transcript.from_event(event).text
                    _LOGGER.info(f"[{self.client_id}] Transcript received: {transcript}")
                    await self._type_text(transcript)
                    # Send transcript back to ESPHome so it knows dictation is complete
                    await self.write_event(event)
                    break
        except Exception as e:
            _LOGGER.error(f"[{self.client_id}] Error reading from Whisper: {e}")
        finally:
            if self.whisper_client:
                await self.whisper_client.disconnect()
                self.whisper_client = None

    async def _type_text(self, text: str):
        if not text.strip():
            _LOGGER.info(f"[{self.client_id}] Transcript was empty, nothing to type.")
            return
            
        safe_text = text.replace('"', '\\"')
        cmd = f"wtype \"{safe_text} \""
        _LOGGER.info(f"[{self.client_id}] Typing text into active window...")
        try:
            proc = await asyncio.create_subprocess_shell(cmd)
            await proc.communicate()
            _LOGGER.info(f"[{self.client_id}] Typed successfully.")
        except Exception as e:
            _LOGGER.error(f"[{self.client_id}] Error typing text: {e}")

    async def disconnect(self):
        _LOGGER.info(f"[{self.client_id}] Connection closed")
        if self.whisper_task:
            self.whisper_task.cancel()
        if self.whisper_client:
            await self.whisper_client.disconnect()
        # Fallback to super().disconnect() is not strictly needed for Wyoming AsyncEventHandler,
        # but let's just make sure we don't crash if it exists
        if hasattr(super(), 'disconnect'):
            await super().disconnect()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=10400)
    parser.add_argument("--whisper-host", default="127.0.0.1")
    parser.add_argument("--whisper-port", type=int, default=10300)
    args = parser.parse_args()

    _LOGGER.info(f"Starting Dixie Dictate server on {args.host}:{args.port}")

    server = AsyncServer.from_uri(f"tcp://{args.host}:{args.port}")
    
    import functools
    handler_factory = functools.partial(DictationHandler, args)
    
    await server.run(handler_factory)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
