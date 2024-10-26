from flask import Flask, session, redirect, request, url_for
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os
import base64
import google.auth.transport.requests
import google.oauth2.credentials
import googleapiclient.discovery
import google.auth.exceptions
import json
import google.generativeai as genai
from dotenv import load_dotenv, dotenv_values
from pymongo import MongoClient
import datetime
from mongo_config import MONGODB_CONFIG
import logging


load_dotenv()
app = Flask(__name__)
app.secret_key = 'arnav'  

# Configure Google OAuth2
CREDENTIALS_FILE = "credentials.json"  # Changed from CLIENT_SECRETS_FILE
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Configure Gemini AI
genai.configure(api_key=os.getenv("GEMINI_token"))
model = genai.GenerativeModel('gemini-1.5-flash')

# Make sure this matches exactly with what you set in Google Cloud Console
REDIRECT_URI = 'http://localhost:5000/oauth2callback'

# MongoDB Configuration
# MongoDB Atlas connection string (replace with your actual connection string)

MONGODB_URI = "MONGODB_URI"
DB_NAME = "email_analysis_db"
COLLECTION_NAME = "email_tasks"

# Initialize MongoDB client

try:
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    print("Connected to MongoDB successfully!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

def get_flow():
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,  # Changed from CLIENT_SECRETS_FILE
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    return flow

@app.route('/')
def index():
    if 'credentials' not in session:
        return '<a href="/authorize">Login with Google</a>'
    return 'You are logged in! <a href="/get_emails">Get Emails</a>'

@app.route('/authorize')
def authorize():
    try:
        flow = get_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        session['state'] = state
        print(f"Authorization URL: {authorization_url}")  # For debugging
        return redirect(authorization_url)
    except Exception as e:
        print(f"Error in authorize: {str(e)}")  # For debugging
        return f"An error occurred: {str(e)}"

@app.route('/oauth2callback')
def oauth2callback():
    try:
        flow = get_flow()
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        print("Credentials saved in session:", session['credentials'])

        return redirect(url_for('index'))
    except Exception as e:
        print(f"Error in oauth2callback: {str(e)}")  # For debugging
        return f"An error occurred: {str(e)}"

def clean_text(text):
    try:
        # Handle None or empty text
        if not text:
            return ""
            
        # Convert bytes to string if needed
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='ignore')
            
        # Replace non-ASCII characters and clean whitespace
        import re
        # First, normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        # Then remove non-ASCII characters
        text = ''.join(char for char in text if ord(char) < 128)
        # Finally, strip leading/trailing whitespace
        text = text.strip()
        
        return text
    except Exception as e:
        print(f"Error in clean_text: {str(e)}")
        return ""

def analyze_email_with_gemini(subject, sender, body):
    try:
        cleaned_subject = clean_text(subject or "No Subject")
        cleaned_sender = clean_text(sender or "No Sender")
        cleaned_body = clean_text(body or "No Body")

        prompt = (
            f"Analyze this email:\n"
            f"Subject: {cleaned_subject}\n"
            f"From: {cleaned_sender}\n"
            f"Body: {cleaned_body}\n\n"
            f"Create a task summary in JSON format with the following fields:\n"
            f"- task (string): Brief description of the main task\n"
            f"- priority (string): High/Medium/Low based on the sentiment of the body, if it is urgent select high, if it is more than 30 days keep priority Low\n"
            f"- due_date (string): Estimated due date based on content\n"
            f"- category (string): Type of task"
            f"Do not provide anything that has not been asked of. There is no need of explanation. Just provide the JSON object."
        )

        response = model.generate_content(prompt)
        
        # Debug print
        print("Gemini Response:", response.text)
        
        # Try to extract JSON from the response
        import re
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            return json.loads(json_str)
        
        # If no JSON found, return default structure
        return {
            "task": "Could not analyze email content",
            "priority": "Low",
            "due_date": "N/A",
            "category": "Unknown"
        }
        
    except Exception as e:
        print(f"Error in analyze_email_with_gemini: {str(e)}")
        return {
            "task": "Error analyzing email",
            "priority": "Low",
            "due_date": "N/A",
            "category": "Error"
        }

@app.route('/get_emails')
def get_emails():
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    try:
        credentials = google.oauth2.credentials.Credentials(**session['credentials'])
        service = build('gmail', 'v1', credentials=credentials)

        results = service.users().messages().list(
            userId='me',
            maxResults=10
        ).execute()
        
        messages = results.get('messages', [])
        analyzed_emails = []

        for message in messages:
            try:
                msg = service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='full'
                ).execute()

                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'No Sender')

                # Extract body
                body = msg.get('snippet', '')  # Start with snippet as fallback
                
                if 'parts' in msg['payload']:
                    for part in msg['payload']['parts']:
                        if part.get('mimeType') == 'text/plain':
                            data = part.get('body', {}).get('data', '')
                            if data:
                                try:
                                    decoded = base64.urlsafe_b64decode(data)
                                    body = decoded.decode('utf-8', errors='ignore')
                                    break
                                except Exception as e:
                                    print(f"Error decoding body part: {str(e)}")
                elif 'body' in msg['payload']:
                    data = msg['payload']['body'].get('data', '')
                    if data:
                        try:
                            decoded = base64.urlsafe_b64decode(data)
                            body = decoded.decode('utf-8', errors='ignore')
                        except Exception as e:
                            print(f"Error decoding body: {str(e)}")

                # Clean and analyze
                cleaned_subject = clean_text(subject)
                cleaned_sender = clean_text(sender)
                cleaned_body = clean_text(body)

                # Debug prints
                print(f"Processing email:")
                print(f"Subject: {cleaned_subject}")
                print(f"From: {cleaned_sender}")
                print(f"Body sample: {cleaned_body[:100]}...")

                analysis = analyze_email_with_gemini(cleaned_subject, cleaned_sender, cleaned_body)
                # Store the analysis in MongoDB
                email_data = {
                    "subject": cleaned_subject,
                    "sender": cleaned_sender
                }

                mongo_id = store_email_analysis(email_data, analysis)

                analyzed_emails.append({
                    "subject": cleaned_subject,
                    "sender": cleaned_sender,
                    "analysis": analysis
                })

            except Exception as e:
                print(f"Error processing individual email: {str(e)}")
                continue

        # Create HTML response
        html_response = """
        <html>
        <head>
            <style>
                .email-card {
                    border: 1px solid #ddd;
                    margin: 10px;
                    padding: 15px;
                    border-radius: 5px;
                    background-color: #f9f9f9;
                }
                .email-subject {
                    color: #2c3e50;
                    margin-bottom: 10px;
                }
                .email-sender {
                    color: #7f8c8d;
                    margin-bottom: 5px;
                }
                .email-analysis {
                    margin-top: 10px;
                }
                .priority-high { color: #e74c3c; }
                .priority-medium { color: #f39c12; }
                .priority-low { color: #27ae60; }
            </style>
        </head>
        <body>
            <h1>Analyzed Emails</h1>
        """

        for email in analyzed_emails:
            priority_class = f"priority-{email['analysis'].get('priority', 'low').lower()}"
            html_response += f"""
            <div class="email-card">
                <h3 class="email-subject">{email['subject']}</h3>
                <p class="email-sender">From: {email['sender']}</p>
                <div class="email-analysis">
                    <p>Task: {email['analysis'].get('task', 'N/A')}</p>
                    <p class="{priority_class}">Priority: {email['analysis'].get('priority', 'N/A')}</p>
                    <p>Due Date: {email['analysis'].get('due_date', 'N/A')}</p>
                    <p>Category: {email['analysis'].get('category', 'N/A')}</p>
                </div>
            </div>
            """

        html_response += "</body></html>"
        print("Responded")
        return html_response

    except Exception as e:
        print(f"Error in get_emails: {str(e)}")
        return redirect(url_for('authorize'))

def store_email_analysis(email_data, analysis):
    try:
        document = {
            "email_subject": email_data["subject"],
            "email_sender": email_data["sender"],
            "task": analysis.get("task", "N/A"),
            "priority": analysis.get("priority", "Low"),
            "due_date": analysis.get("due_date", "N/A"),
            "category": analysis.get("category", "Unknown"),
            "created_at": datetime.datetime.utcnow()
        }
        
        result = collection.insert_one(document)
        print(f"Analysis stored in MongoDB with ID: {result.inserted_id}")
        return result.inserted_id
    except Exception as e:
        print(f"Error storing analysis in MongoDB: {e}")
        return None

@app.route('/view_stored_analyses')
def view_stored_analyses():
    try:
        stored_analyses = list(collection.find().sort("created_at", -1))
        
        html_response = """
        <html>
        <head>
            <style>
                /* ... [previous styles] ... */
            </style>
        </head>
        <body>
            <h1>Stored Email Analyses</h1>
        """

        for analysis in stored_analyses:
            priority_class = f"priority-{analysis.get('priority', 'low').lower()}"
            html_response += f"""
            <div class="email-card">
                <h3 class="email-subject">{analysis.get('email_subject', 'No Subject')}</h3>
                <p class="email-sender">From: {analysis.get('email_sender', 'No Sender')}</p>
                <div class="email-analysis">
                    <p>Task: {analysis.get('task', 'N/A')}</p>
                    <p class="{priority_class}">Priority: {analysis.get('priority', 'N/A')}</p>
                    <p>Due Date: {analysis.get('due_date', 'N/A')}</p>
                    <p>Category: {analysis.get('category', 'N/A')}</p>
                    <p>Stored: {analysis.get('created_at', 'N/A')}</p>
                </div>
            </div>
            """

        html_response += "</body></html>"
        return html_response

    except Exception as e:
        print(f"Error retrieving stored analyses: {e}")
        return "Error retrieving stored analyses"
    
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1' 


if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # For development only
    app.run(host='localhost', port=5000, debug=True)