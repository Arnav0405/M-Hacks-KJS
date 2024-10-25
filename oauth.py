import os
import base64
import json
import google.auth
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Modify authenticate_gmail function
from google_auth_oauthlib.flow import InstalledAppFlow

def authenticate_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            # Run the local server on port 8000 to match the redirect URI
            creds = flow.run_local_server(port=8080)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def fetch_emails():
    try:
        service = authenticate_gmail()

        profile = service.users().getProfile(userId='me').execute()
        user_email = profile['emailAddress']

        # Check if the email belongs to somaiya.edu domain
        if not user_email.endswith('@somaiya.edu'):
            print("Access denied: Only somaiya.edu accounts are allowed.")
            return


        results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=10).execute()
        messages = results.get('messages', [])
        if not messages:
            print("No new messages found.")
            return
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            print("Message snippet:", msg['snippet'])
            print("\n")
    except HttpError as error:
        print(f"An error occurred: {error}")

if __name__ == '__main__':
    try:
        fetch_emails()
    finally:
        print("Closing script and freeing resources.")
