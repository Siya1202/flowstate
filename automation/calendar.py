import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pickle

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_PATH = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", "./credentials/google_calendar.json")
TOKEN_PATH = "./credentials/token.pickle"

def get_calendar_service():
    """Authenticate and return Google Calendar service."""
    creds = None

    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "wb") as token:
            pickle.dump(creds, token)

    return build("calendar", "v3", credentials=creds)

def create_calendar_event(task_title: str, owner: str, deadline: str) -> dict:
    """Create a Google Calendar event for a task."""
    service = get_calendar_service()

    # Parse deadline or default to tomorrow
    try:
        start_time = datetime.fromisoformat(deadline)
    except (ValueError, TypeError):
        start_time = datetime.now() + timedelta(days=1)

    end_time = start_time + timedelta(hours=1)

    event = {
        "summary": f"[Flowstate] {task_title}",
        "description": f"Task assigned to: {owner}\nCreated by Flowstate AI",
        "start": {"dateTime": start_time.isoformat(), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "Asia/Kolkata"},
    }

    created_event = service.events().insert(calendarId="primary", body=event).execute()
    print(f" Calendar event created: {created_event.get('htmlLink')}")
    return created_event