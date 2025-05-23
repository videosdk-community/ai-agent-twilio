from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# from typing import List, Optional
# import uvicorn
import os
# import json
# import requests
import logging
import httpx
import asyncio
from fastapi import Request, Response, HTTPException, FastAPI
from twilio.twiml.voice_response import VoiceResponse
from twilio.request_validator import RequestValidator
from dotenv import load_dotenv
from twilio.rest import Client
from openai_agent_quickstart import main as openai_agent_main
# VideoSDKAgent
from agent import VideoSDKAgent
# Add this at the top with other imports

# Add after your imports
class CallRequest(BaseModel):
    phoneNumber: str
    meetingId: str = None

# Load environment variables from .env file
load_dotenv()


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Environment Variable Checks ---
VIDEOSDK_SIP_USERNAME = os.getenv("VIDEOSDK_SIP_USERNAME")
VIDEOSDK_SIP_PASSWORD = os.getenv("VIDEOSDK_SIP_PASSWORD")
VIDEOSDK_AUTH_TOKEN = os.getenv("VIDEOSDK_AUTH_TOKEN")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
BASE_URL = os.getenv("BASE_URL")
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

validator = RequestValidator(TWILIO_AUTH_TOKEN)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)



# --- Helper Function to Create VideoSDK Room ---
async def create_videosdk_room() -> str:
    """
    Calls the VideoSDK API to create a new room.
    Returns the roomId if successful, raises HTTPException otherwise.
    """
    if not VIDEOSDK_AUTH_TOKEN:
         logging.error("VideoSDK Auth Token is not configured.")
         raise HTTPException(status_code=500, detail="Server configuration error [VSDK Token]")

    headers = {"Authorization": VIDEOSDK_AUTH_TOKEN}

    async with httpx.AsyncClient() as client:
        try:
            logging.info(f"Attempting to create VideoSDK room at v2/rooms")
            response = await client.post("https://api.videosdk.live/v2/rooms", headers=headers, timeout=10.0)
            response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx responses

            response_data = response.json()
            room_id = response_data.get("roomId")

            if not room_id:
                logging.error(f"VideoSDK response missing 'roomId'. Response: {response_data}")
                raise HTTPException(status_code=500, detail="Failed to get roomId from VideoSDK")

            logging.info(f"Successfully created VideoSDK room: {room_id}")
            return room_id

        except httpx.RequestError as exc:
            logging.error(f"HTTP Request to VideoSDK failed: {exc}")
            raise HTTPException(status_code=503, detail=f"Could not reach VideoSDK service: {exc}")
        except httpx.HTTPStatusError as exc:
            logging.error(f"VideoSDK API error: Status {exc.response.status_code}, Response: {exc.response.text}")
            raise HTTPException(status_code=exc.response.status_code, detail=f"VideoSDK API Error: {exc.response.text}")
        except Exception as exc:
            logging.error(f"An unexpected error occurred during VideoSDK room creation: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Internal server error creating room: {exc}")

# --- Twilio Webhook Endpoint ---
@app.post("/join-agent", response_class=Response)
async def handle_twilio_call(request: Request):
    """
    Handles incoming Twilio call webhook.
    Creates a VideoSDK room and returns TwiML to connect the call via SIP.
    """
    # --- VALIDATE TWILIO REQUEST ---
    form_data = await request.form()
    twilio_signature = request.headers.get('X-Twilio-Signature', None)
   
    room_id = "hzm6-7i1y-mfbv"
    agent_token = VIDEOSDK_AUTH_TOKEN # later will be generate via api
    
    # --- Step 2: Instantiate and Connect Agent (in background) ---

    if room_id and agent_token:
        logger.info(f"Step 2: Initializing and connecting agent for room {room_id}")
        agent = VideoSDKAgent(room_id=room_id, videosdk_token=agent_token, agent_name="SIP DUMB USER")

        # Run the agent's connect method in the background
        asyncio.create_task(agent.connect())         
        logger.info(f"Agent connection task created for room {room_id}")
    else:
         logger.error("Cannot proceed with agent connection, room_id or agent_token missing.")
         

    # --- Step 3: Generate TwiML to connect to VideoSDK SIP ---
    sip_uri = f"sip:{room_id}@sip.videosdk.live"
    logging.info(f"Connecting caller to SIP URI: {sip_uri}")

    response = VoiceResponse()
    # Optional: Announce connecting
    response.say("Thank you for calling. Connecting you to the meeting now.")

    # Create the <Dial> verb with the <Sip> noun
    dial = response.dial(caller_id=None) # You might need to set caller_id depending on Twilio/SIP setup
    dial.sip(sip_uri, username=VIDEOSDK_SIP_USERNAME, password=VIDEOSDK_SIP_PASSWORD)

    # If the SIP call fails or doesn't answer, you can add fallback instructions
    # response.say("The connection failed or was not answered.")
    # response.hangup() # Or redirect, etc.

    logging.info("Generated TwiML for SIP connection.")
    # Return the TwiML response to Twilio
    

    return Response(content=str(response), media_type="application/xml")

@app.post("/outbound-call")
async def make_outbound_call(request: CallRequest):
    print("Making outbound call")
    try:
        webhook_url =f"{BASE_URL}/join-agent"  # Replace with your actual webhook URL

        # if not request.phoneNumber:
        #     raise HTTPException(status_code=400, detail="Phone number is required!")

        # Make the outbound call
        call = client.calls.create(
            to="+919601191997",
            from_="+12299999925",
            url=webhook_url,
            method="POST"
        )

        print("Call initiated successfully", call)

        return {
            "success": True,
            "callSid": call.sid
        }

    except Exception as error:
        print(f"Error making outbound call: {error}")
        # Return dictionary directly
        return {
            "success": False,
            "error": "Failed to initiate call"
        }



@app.get("/")
def read_root():
    return {"Hello": "World"}

# --- Run the server (for local development) ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000)) # Allow PORT env var for deployment flexibility
    logging.info(f"Starting server on http://0.0.0.0:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)