from videosdk import (
    VideoSDK,
    Meeting,
    MeetingConfig,
    MeetingEventHandler,
    ParticipantEventHandler,
    Stream,
    Participant
)
import asyncio
import os
from openai_agent_quickstart import main as openai_agent_main
import logging

logger = logging.getLogger(__name__) # use a specific logger

VIDEOSDK_AUTH_TOKEN = os.getenv("VIDEOSDK_AUTH_TOKEN")

class AgentParticipantEventHandler(ParticipantEventHandler):
    """Handles events specific to a participant within the meeting for the Agent."""
    def __init__(self, agent_name: str, participant: Participant):
        self.agent_name = agent_name
        self.participant = participant
        logger.info(f"[{self.agent_name}] ParticipantEventHandler initialized.")

    def on_stream_enabled(self, stream: Stream) -> None:
        """Handle Participant stream enabled event."""
     
        logger.info(
            f"[{self.agent_name}] Stream ENABLED: Kind='{stream.kind}', "
            f"StreamId='{stream.id}', ParticipantId='{self.participant.id}', "
            f"ParticipantName='{self.participant.display_name}'"
        )
        # --- CRITICAL: Process Audio Stream ---
        if stream.kind == "audio" and not self.participant.local: # Process remote audio
            logger.info(f"[{self.agent_name}] ===> Received AUDIO stream from {self.participant.display_name} ({self.participant.id})")
            # TODO: Implement audio stream processing/logging here.
            # How to access the actual audio data from the 'stream' object?
            # This likely requires more specific SDK methods or callbacks
            # associated with the stream object itself.
            # Example Placeholder: asyncio.create_task(self.process_audio_stream(stream))
            pass

    def on_stream_disabled(self, stream: Stream) -> None:
        """Handle Participant stream disabled event."""
        logger.info(
            f"[{self.agent_name}] Stream DISABLED: Kind='{stream.kind}', "
            f"StreamId='{stream.id}', ParticipantId='{self.participant.id}', "
            f"ParticipantName='{self.participant.display_name}'"
        )
        if stream.kind == "audio" and not self.participant.local:
            logger.info(f"[{self.agent_name}] ===> Stopped receiving AUDIO stream from {self.participant.display_name} ({self.participant.id})")
            # TODO: Stop any corresponding audio processing task for this stream.
            pass

    # Add other ParticipantEventHandler methods if needed (on_media_status_changed, etc.)


class AgentMeetingEventHandler(MeetingEventHandler):
    """Handles meeting-level events for the Agent."""
    def __init__(self, agent_name: str, agent_instance: 'VideoSDKAgent'):
        self.agent_name = agent_name
        self.agent_instance = agent_instance # Reference to the agent itself
        logger.info(f"[{self.agent_name}] MeetingEventHandler initialized.")

    def on_meeting_joined(self, data) -> None:
        logger.info(f"[{self.agent_name}] Successfully JOINED meeting.")

    def on_meeting_left(self, data) -> None:
        logger.warning(f"[{self.agent_name}] LEFT meeting.")
        # Perform cleanup if needed, maybe notify main app
        self.agent_instance.mark_disconnected() # Update agent state

def on_participant_joined(self, participant: Participant) -> None:
    logger.info(
            f"[{self.agent_name}] Participant JOINED: Id='{participant.id}', "
            f"Name='{participant.display_name}', IsLocal={participant.local}"
    )
        
    if participant.display_name == "SIP User":
            print("SIP USER joined")
            self.agent_instance.ai_agent_task = asyncio.create_task(openai_agent_main(context))
            self.agent_instance.ai_agent_task.add_done_callback(lambda task: print("Agent task completed"))
    else:
            print("SIP USER not joined")

    def on_participant_left(self, participant: Participant) -> None:
        logger.warning(
            f"[{self.agent_name}] Participant LEFT: Id='{participant.id}', "
            f"Name='{participant.display_name}'"
        )
        # TODO: Check if this is the SIP user. If so, maybe trigger agent disconnect?
        # Cleanup participant event handler
        if participant.id in self.agent_instance.participant_handlers:
            handler_to_remove = self.agent_instance.participant_handlers.pop(participant.id)
            participant.remove_event_listener(handler_to_remove)
            logger.debug(f"[{self.agent_name}] Removed event handler for participant {participant.id}")

        # Optionally, if the *only* other participant leaves, the agent could leave too
        # if len(self.agent_instance.meeting.participants) <= 1: # Check logic carefully
        #    logger.warning(f"[{self.agent_name}] Last participant left. Leaving meeting.")
        #    asyncio.create_task(self.agent_instance.disconnect())


    def on_error(self, data):
        logger.error(f"[{self.agent_name}] Meeting Error: {data}")
        # Handle specific errors if possible


class VideoSDKAgent:
    """Represents an AI Agent connected to a VideoSDK meeting."""

    def __init__(self, room_id: str, videosdk_token: str, agent_name: str = "AI Assistant"):
        self.room_id = room_id
        self.videosdk_token = videosdk_token
        self.agent_name = agent_name
        self.meeting: Meeting | None = None
        self.is_connected = False
        self.participant_handlers = {} # Store participant handlers for cleanup
        self.ai_agent_task = None  # Add this to store the AI agent task

        logger.info(f"[{self.agent_name}] Initializing for Room ID: {self.room_id}")
        self._initialize_meeting()

    def _initialize_meeting(self):
        """Sets up the Meeting object using VideoSDK.init_meeting."""
        try:
            # Configure the agent's meeting settings
            meeting_config: MeetingConfig = {
                "meeting_id": self.room_id,
                "token": self.videosdk_token,
                "name": self.agent_name,
                "mic_enabled": False,         # Agent doesn't speak initially
                "webcam_enabled": False,      # Agent has no camera
                "auto_consume": True,         # Automatically receive streams from others
                # Add other relevant config from MeetingConfig if needed
                # e.g. custom_microphone_audio_track if agent needs to send audio later
            }
            logger.debug(f"[{self.agent_name}] Meeting Config: {meeting_config}")

            self.meeting = VideoSDK.init_meeting(**meeting_config)

            # Attach event handlers
            meeting_event_handler = AgentMeetingEventHandler(self.agent_name, self)
            self.meeting.add_event_listener(meeting_event_handler)

            logger.info(f"[{self.agent_name}] Meeting object initialized.")

        except Exception as e:
            logger.exception(f"[{self.agent_name}] Failed to initialize VideoSDK Meeting: {e}")
            self.meeting = None # Ensure meeting is None if init fails

    async def connect(self):
        """Connects the agent to the meeting asynchronously."""
        if not self.meeting:
            logger.error(f"[{self.agent_name}] Cannot connect, meeting not initialized.")
            return

        if self.is_connected:
            logger.warning(f"[{self.agent_name}] Already connected or connecting.")
            return

        logger.info(f"[{self.agent_name}] Attempting to join meeting...")
        try:
            await self.meeting.async_join()
            # Note: on_meeting_joined event confirms connection
            self.is_connected = True # Mark as connected (or better, set in on_meeting_joined)
            logger.info(f"[{self.agent_name}] async_join call completed (waiting for on_meeting_joined event).")
            # Keep running until disconnected
            # This might need a more sophisticated mechanism depending on how the SDK handles background tasks
        except Exception as e:
            logger.exception(f"[{self.agent_name}] Error during async_join: {e}")
            self.is_connected = False

    async def disconnect(self):
        """Disconnects the agent from the meeting."""
        if not self.meeting or not self.is_connected:
            logger.warning(f"[{self.agent_name}] Cannot disconnect, not connected or meeting not initialized.")
            return

        logger.info(f"[{self.agent_name}] Leaving meeting...")
        try:
            # Cancel the AI agent task if it exists
            if self.ai_agent_task and not self.ai_agent_task.done():
                self.ai_agent_task.cancel()
                try:
                    await self.ai_agent_task
                except asyncio.CancelledError:
                    pass
                self.ai_agent_task = None

            # End the meeting
            self.meeting.end()
        except Exception as e:
            logger.exception(f"[{self.agent_name}] Error during leave/end: {e}")
        finally:
            self.participant_handlers.clear()

    def mark_disconnected(self):
        """Callback for event handler to update state."""
        self.is_connected = False
        logger.info(f"[{self.agent_name}] Marked as disconnected.")

    # --- Placeholder for Audio Processing ---
    # async def process_audio_stream(self, stream: Stream):
    #     logger.info(f"[{self.agent_name}] Starting to process audio stream {stream.id} from {stream.participant.display_name}")
    #     try:
    #         # This is where you'd interact with the stream object
    #         # to get audio chunks/data based on the SDK's API.
    #         # Example (pseudo-code, depends heavily on SDK):
    #         # async for audio_chunk in stream.listen_for_audio():
    #         #     logger.debug(f"Received audio chunk: {len(audio_chunk)} bytes")
    #         #     # Process/log the chunk
    #         await asyncio.sleep(3600) # Keep task alive for testing
    #     except asyncio.CancelledError:
    #          logger.info(f"[{self.agent_name}] Audio processing task cancelled for stream {stream.id}")
    #     except Exception as e:
    #          logger.exception(f"[{self.agent_name}] Error processing audio stream {stream.id}: {e}")
    #     finally:
    #          logger.info(f"[{self.agent_name}] Finished processing audio stream {stream.id}")