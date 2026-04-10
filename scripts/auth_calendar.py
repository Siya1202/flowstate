from automation.calendar import get_calendar_service

if __name__ == "__main__":
    print("Starting Google Calendar auth flow...")
    service = get_calendar_service()
    print("Authentication successful!")
    
    # Test by listing upcoming events
    events_result = service.events().list(
        calendarId="primary",
        maxResults=5
    ).execute()
    events = events_result.get("items", [])
    
    if not events:
        print("No upcoming events found.")
    else:
        print("Upcoming events:")
        for event in events:
            print(f"  - {event['summary']}")