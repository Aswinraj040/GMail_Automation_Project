import base64
import sqlite3
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from dotenv import load_dotenv
import os

# Load variables from .env file
load_dotenv()

# Read environment variables
SCOPES = os.getenv("SCOPES").split(",")
DB_NAME = os.getenv("DB_NAME")
TABLE_NAME = os.getenv("TABLE_NAME")
LOG_FILE = os.getenv("FETCH_LOG_FILE")
EMAIL_SIZE = os.getenv("EMAIL_SIZE", "50")  # Default to 50 if not set
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, os.getenv("CREDENTIALS_FILE"))
TOKENS_FILE = os.path.join(BASE_DIR, os.getenv("TOKENS_FILE"))

def log_error(message):
    """
    Logs error messages with a timestamp to fetch_emails.log.
    Args:
        message (str): The error message to log
    """
    timestamp = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    with open(LOG_FILE, 'a') as log_file:
        log_file.write(f"[{timestamp}] {message}\n")


def authenticate_gmail():
    """
    Handles authentication with the Gmail API using OAuth 2.0.
    Reuses saved credentials if available, otherwise initiates a new login flow.
    Returns:
        service: Authorized Gmail API service instance
    """
    try:
        creds = None

        # Load credentials from token file if it exists
        if os.path.exists(TOKENS_FILE):
            creds = Credentials.from_authorized_user_file(TOKENS_FILE, SCOPES)

        # If no valid credentials, start the OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Refresh the access token using the refresh token
                creds.refresh(Request())
            else:
                # Start a new authentication flow to get new credentials
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the new credentials for future use
            with open(TOKENS_FILE, 'w') as token:
                token.write(creds.to_json())

        # Build and return the Gmail API service object
        gmail_service = build('gmail', 'v1', credentials=creds)
        return gmail_service
    except Exception as e:
        log_error(f"Gmail authentication failed: {e}")
        raise


def setup_database():
    """
    Initializes the SQLite database and ensures the Emails table exists.
    Clears any existing data to avoid duplicates on each run.
    Returns:
        conn: SQLite connection object
        c: SQLite cursor object
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # Create the Emails table if it doesn't already exist
        c.execute(f'''
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                gmail_id TEXT PRIMARY KEY,
                sender TEXT,
                recipient TEXT,
                subject TEXT,
                message TEXT,
                date TEXT
            )
        ''')

        # Clear previous records to refresh with latest fetched emails
        c.execute(f'DELETE FROM {TABLE_NAME}')
        conn.commit()
        return conn, c
    except Exception as e:
        if conn:
            conn.close()
        log_error(f"Database setup failed: {e}")
        raise


def format_email_date(date_str):
    """
    Converts RFC 2822-style email date string to IST (UTC+5:30) formatted string.
    Falls back to original string on parsing error.
    Args:
        date_str (str): Raw date string from email header
    Returns:
        str: Formatted date string in 'DD/MM/YYYY HH:MM:SS' or original string on failure
    """
    try:
        # Parse the date using common RFC format, ignoring timezone info
        date_obj = datetime.datetime.strptime(date_str[:25], '%a, %d %b %Y %H:%M:%S')

        # Apply IST timezone offset
        offset = datetime.timedelta(hours=5, minutes=30)
        ist_datetime = date_obj + offset

        return ist_datetime.strftime('%d/%m/%Y %H:%M:%S')
    except Exception as e:
        log_error(f"Date formatting failed for '{date_str}': {e}")
        return date_str


def extract_message_body(payload):
    """
    Extracts and decodes the plain text body from the email payload.
    Supports both direct body and MIME multipart structures.
    Args:
        payload (dict): The email payload section from Gmail API
    Returns:
        str: Decoded message text
    """
    try:
        # Handle single-part message with data in 'body'
        if 'data' in payload.get('body', {}):
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

        # Handle multi-part messages, prefer plain text
        for part in payload.get('parts', []):
            if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
    except Exception as e:
        log_error(f"Message body extraction failed: {e}")

    return ''  # Fallback if message can't be decoded

def fetch_emails(gmail_service, max_results):
    """
    Fetches emails from the Gmail inbox, extracts relevant fields,
    and stores them in a local SQLite database.
    """
    conn = None
    try:
        conn, cursor = setup_database()

        results = gmail_service.users().messages().list(
            userId='me', labelIds=['INBOX'], maxResults=max_results).execute()
        messages = results.get('messages', [])

        total = len(messages)
        for index, msg in enumerate(messages, start=1):
            try:
                msg_data = gmail_service.users().messages().get(userId='me', id=msg['id']).execute()
                payload = msg_data.get('payload', {})
                headers = payload.get('headers', [])

                subject = sender = recipient = date_str = ""
                message = extract_message_body(payload)
                gmail_id = msg['id']

                for header in headers:
                    if header['name'] == 'Subject':
                        subject = header['value']
                    elif header['name'] == 'From':
                        sender = header['value']
                    elif header['name'] == 'To':
                        recipient = header['value']
                    elif header['name'] == 'Date':
                        date_str = header['value']

                formatted_date = format_email_date(date_str)

                cursor.execute(f'''
                    INSERT OR REPLACE INTO {TABLE_NAME} (
                        gmail_id, sender, recipient, subject, message, date
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (gmail_id, sender, recipient, subject, message, formatted_date))

                print(f"[✓] Fetched and stored email {index} of {total} — Subject: \"{subject}\"")

            except Exception as inner_e:
                log_error(f"Failed to process message ID {msg.get('id')}: {inner_e}")

        conn.commit()
        print("\n[INFO] All emails processed and stored successfully.")

    except Exception as e:
        log_error(f"Email fetching failed: {e}")
        raise

    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Entry point: Authenticate and fetch emails
    service = authenticate_gmail()
    fetch_emails(service , EMAIL_SIZE)
