import json
import os
import sqlite3
import datetime
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
load_dotenv()

# SQLite database name
EMAIL_DB_NAME = os.getenv("DB_NAME")

# Gmail API OAuth scopes
GMAIL_SCOPES = os.getenv("SCOPES", "").split(",")
# Base directory for relative paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Path to credentials file for Gmail API
CREDENTIALS_FILE = os.path.join(BASE_DIR, os.getenv("CREDENTIALS_FILE"))
# Log file for processing emails
PROCESS_LOG_FILE = os.getenv("PROCESS_LOG_FILE")
# Path to tokens file for Gmail API
TOKENS_FILE = os.path.join(BASE_DIR, os.getenv("TOKENS_FILE"))

RULES_FILE_PATH = os.path.join(BASE_DIR, os.getenv("RULES_FILE"))



def log_error(message):
    """
    Logs error messages with a timestamp to fetch_emails.log.
    Args:
        message (str): The error message to log
    """
    timestamp = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    with open(PROCESS_LOG_FILE, 'a') as log_file:
        log_file.write(f"[{timestamp}] {message}\n")


def authenticate_gmail():
    """
    Authenticate with the Gmail API using OAuth 2.0.
    Reuses saved credentials if valid; otherwise initiates the OAuth flow.
    Returns:
        service: Authenticated Gmail API service instance
    """
    try:
        creds = None

        # Load existing token if available
        if os.path.exists(TOKENS_FILE):
            creds = Credentials.from_authorized_user_file(TOKENS_FILE, GMAIL_SCOPES)

        # If credentials are missing or invalid, refresh or start new flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, GMAIL_SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the updated credentials for reuse
            with open('../token.json', 'w') as token:
                token.write(creds.to_json())

        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        log_error(f"Gmail authentication failed: {e}")
        raise



def load_rules():
    """
    Load rule sets from the external JSON configuration file.
    Returns:
        List of rule dictionaries from the "All Rules" key
    """
    try:
        with open(RULES_FILE_PATH, 'r') as file:
            data = json.load(file)
            return data.get("all_rules", [])
    except Exception as e:
        log_error(f"Error opening json: {e}")
        raise


def match_condition(value, predicate, expected):
    """
    Evaluates a single rule condition against a field's value.
    Supports string matching and date comparisons.
    Args:
        value (str): The actual value from the email
        predicate (str): Type of comparison (e.g., 'contains', 'less_than')
        expected (str): Expected value or threshold (e.g., '3_days', '2_months')
    Returns:
        bool: Whether the condition matches
    """
    try:
        value = str(value or '')  # Normalize None to empty string
        expected = str(expected)

        #print(f"[DEBUG] Matching value: '{value}' with expected: '{expected}' using predicate: '{predicate}'")

        if predicate == 'contains':
            return expected.lower() in value.lower()
        elif predicate == 'does_not_contain':
            return expected.lower() not in value.lower()
        elif predicate == 'equals':
            return value.strip().lower() == expected.strip().lower()
        elif predicate == 'does_not_equal':
            return value.strip().lower() != expected.strip().lower()
        elif predicate in ['less_than', 'greater_than']:
            try:
                # Parse the email's date
                email_date = datetime.datetime.strptime(value, '%d/%m/%Y %H:%M:%S')

                # Split expected format like "3_days" or "2_months"
                amount, unit = expected.lower().split('_')
                amount = int(amount)

                # Handle days and months (30 days approximation)
                if unit == 'days':
                    delta = datetime.timedelta(days=amount)
                elif unit == 'months':
                    delta = datetime.timedelta(days=amount * 30)
                else:
                    raise ValueError(f"Unsupported time unit: {unit}")

                # Determine cutoff date
                cutoff = datetime.datetime.now() - delta

                return email_date > cutoff if predicate == 'less_than' else email_date < cutoff

            except Exception as e:
                #print(f"[ERROR] Date parsing error or invalid expected format: {e}")
                return False

        return False  # Unknown predicate fallback
    except Exception as e:
        log_error(f"Error while matching condition: {e}")
        raise




def evaluate_rules(email, rules):
    """
    Evaluates a set of rules against a given email's fields.
    Args:
        email (dict): Email data from the database
        rules (dict): Rule set with conditions and predicate ('all' or 'any')
    Returns:
        bool: True if the email matches the rule set
    """
    try:
        match_type = rules.get('predicate', 'all').lower()
        rule_results = []

        #print(f"\n[INFO] Evaluating Email: {email.get('subject', '')}")

        for rule in rules['rules']:
            field = rule['field'].lower()
            predicate = rule['predicate'].lower()
            expected = rule['value']
            actual_value = email.get(field, '')

            result = match_condition(actual_value, predicate, expected)
            #(f"[RULE] IF {field} {predicate} '{expected}' → VALUE: '{actual_value}' → Match: {result}")
            rule_results.append(result)

        # Combine results using logical AND / OR based on rule type
        match = all(rule_results) if match_type == 'all' else any(rule_results)
        if match:
            print(f"[INFO] Rule matched for Email: {email.get('subject', '')}")
        return match
    except Exception as e:
        log_error(f"Error while evaluating json: {e}")
        raise



def apply_actions(service, msg_id, actions):
    """
    Applies Gmail actions (e.g., move to label, mark read) to a given message.
    Args:
        service: Authenticated Gmail API service instance
        msg_id (str): Gmail message ID
        actions (list): List of string-based actions to perform
    """

    for action in actions:
        try:
            add_labels = []
            remove_labels = []
            action_lower = action.lower()

            if action_lower == 'mark_as_read':
                remove_labels.append('UNREAD')
                #print(f"[ACTION] Preparing to mark as READ → Message ID: {msg_id}")

            elif action_lower == 'mark_as_unread':
                add_labels.append('UNREAD')
                #print(f"[ACTION] Preparing to mark as UNREAD → Message ID: {msg_id}")

            elif action_lower == 'move_to:starred':
                add_labels.append('STARRED')
                #print(f"[ACTION] Preparing to mark as STARRED → Message ID: {msg_id}")

            elif action_lower == 'move_to:important':
                add_labels.append('IMPORTANT')
                #print(f"[ACTION] Preparing to mark as IMPORTANT → Message ID: {msg_id}")

            elif action_lower == 'move_to:trash':
                # Move email to trash using Gmail API
                service.users().messages().trash(userId='me', id=msg_id).execute()
                #print(f"[ACTION] Moved to TRASH → Message ID: {msg_id}")
                continue  # Skip label modifications

            elif action_lower.startswith('move_to:'):
                label_name = action.split(':', 1)[1].strip()

                # Avoid interfering with Gmail system labels directly
                if label_name.lower() in ['starred', 'important', 'trash']:
                    continue

                # Create label if it doesn't exist
                label_id = get_or_create_label(service, label_name)
                add_labels.append(label_id)
                remove_labels.append('INBOX')
                #print(f"[ACTION] Preparing to move to label '{label_name}' → Message ID: {msg_id}")

            # If labels need to be added/removed, send modification request
            if add_labels or remove_labels:
                body = {}
                if add_labels:
                    body['addLabelIds'] = add_labels
                if remove_labels:
                    body['removeLabelIds'] = remove_labels

                service.users().messages().modify(userId='me', id=msg_id, body=body).execute()
                #print(f"[ACTION] Labels updated for Message ID: {msg_id} → Add: {add_labels}, Remove: {remove_labels}")

        except Exception as e:
            log_error(f"[ERROR] Failed action '{action}' on message {msg_id}: {e}")


def get_or_create_label(service, label_name):
    """
    Retrieves an existing label ID or creates a new label if it doesn't exist.
    Args:
        service: Authenticated Gmail API service instance
        label_name (str): Name of the Gmail label
    Returns:
        str: Gmail label ID
    """

    try:
        labels = service.users().labels().list(userId='me').execute().get('labels', [])
        for label in labels:
            if label['name'].lower() == label_name.lower():
                return label['id']

        # Create a new label with standard visibility settings
        new_label = service.users().labels().create(userId='me', body={
            'name': label_name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }).execute()
        #print(f"[INFO] Created label: {label_name}")
        return new_label['id']
    except Exception as e:
        log_error(f"Error while creating label: {e}")
        raise



def fetch_emails_from_db():
    """
    Fetches all emails stored in the local SQLite database.
    Returns:
        list of dict: List of email records with field names
    """
    conn = None
    try:
        conn = sqlite3.connect(EMAIL_DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Emails")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        # Convert rows to list of dictionaries
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        log_error(f"Error while fetching emails from db: {e}")
        raise
    finally:
        conn.close()


def process_emails():
    """
    Main processing function:
    - Authenticates Gmail API
    - Loads rule sets
    - Fetches emails from the local database
    - Evaluates rules for each email
    - Applies corresponding actions on matched messages
    """

    try:
        service = authenticate_gmail()
        all_rule_sets = load_rules()
        emails = fetch_emails_from_db()

        for email in emails:
            applied_any_rule = False

            # Evaluate email against all rule sets
            for rule_set in all_rule_sets:
                if evaluate_rules(email, rule_set):
                    #print(f"[INFO] → Rule matched. Applying actions to: {email.get('subject')}")
                    #print(f"[DEBUG] Message ID: {email.get('gmail_id')}")
                    apply_actions(service, email['gmail_id'], rule_set.get('actions', []))
                    applied_any_rule = True
                    break  # Stop evaluating further rules if one matches

            #if not applied_any_rule:
                #print(f"[INFO] → No matching rule found for: {email.get('subject')}")
    except Exception as e:
        log_error(f"Error while processing emails: {e}")
        raise


if __name__ == '__main__':
    process_emails()
