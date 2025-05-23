import asyncio
import aiohttp
from videosdk.agents import Agent, AgentSession, RealTimePipeline, function_tool
from videosdk.plugins.openai import OpenAIRealtime, OpenAIRealtimeConfig
from openai.types.beta.realtime.session import InputAudioTranscription, TurnDetection
import os
from dotenv import load_dotenv

load_dotenv()

VIDEOSDK_AUTH_TOKEN = os.getenv("VIDEOSDK_AUTH_TOKEN")


class MyVoiceAgent(Agent):
    def __init__(self):
        super().__init__(
    instructions=""" You are a helpful assistant. """
        )

    async def on_enter(self) -> None:
        await self.session.say("Hello, how are you?")
    
    async def on_exit(self) -> None:
        await self.session.say("Goodbye!")
            

async def main(context: dict):
    model = OpenAIRealtime(
        model="gpt-4o-realtime-preview",
        config=OpenAIRealtimeConfig(
            modalities=["text", "audio"],
            input_audio_transcription=InputAudioTranscription(model="whisper-1"),
            turn_detection=TurnDetection(
                type="server_vad",
                threshold=0.5,
                prefix_padding_ms=300,
                silence_duration_ms=200,
            ),
            tool_choice="auto",
        )
    )
    pipeline = RealTimePipeline(model=model)
    session = AgentSession(
        agent=MyVoiceAgent(),
        pipeline=pipeline,
        context=context
    )

    try:
        await session.start()
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        await session.close()

if __name__ == "__main__":

    def make_context():
      return {"meetingId": "hzm6-7i1y-mfbv", "name": "OpenAI Agent", "videosdk_auth": VIDEOSDK_AUTH_TOKEN}
    
    asyncio.run(main(context=make_context()))
