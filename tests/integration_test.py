import os
import sqlite3
import unittest
import json
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import src.fetch_emails as fetch_emails
import src.process_emails as process_emails

class IntegrationTestEmailProcessing(unittest.TestCase):
    DB_NAME = 'IntegrationTestEmailDatabase.db'
    RULES_FILE = 'integration_rules.json'
    LOG_FILE = 'integration_test.log'

    def setUp(self):
        # Setup test DB and rules file
        fetch_emails.DB_NAME = self.DB_NAME
        fetch_emails.TABLE_NAME = 'Emails'
        fetch_emails.LOG_FILE = self.LOG_FILE
        process_emails.DB_NAME = self.DB_NAME
        process_emails.LOG_FILE = self.LOG_FILE
        process_emails.RULES_FILE = self.RULES_FILE
        if os.path.exists(self.DB_NAME):
            os.remove(self.DB_NAME)
        if os.path.exists(self.LOG_FILE):
            os.remove(self.LOG_FILE)
        # Create a test rules file
        rules = {
            "all_rules": [
                {
                    "predicate": "All",
                    "rules": [
                        {"field": "sender", "predicate": "contains", "value": "test@domain.com"}
                    ],
                    "actions": ["mark_as_read"]
                }
            ]
        }

        with open(self.RULES_FILE, 'w') as f:
            json.dump(rules, f)

    def tearDown(self):
        if os.path.exists(self.DB_NAME):
            os.remove(self.DB_NAME)
        if os.path.exists(self.RULES_FILE):
            os.remove(self.RULES_FILE)
        if os.path.exists(self.LOG_FILE):
            os.remove(self.LOG_FILE)

    @patch('src.fetch_emails.authenticate_gmail')
    def test_fetch_and_store_emails_integration(self, mock_auth):
        # Mock Gmail API service
        mock_service = MagicMock()
        mock_auth.return_value = mock_service
        mock_service.users().messages().list().execute.return_value = {
            'messages': [{'id': '1'}]
        }
        mock_service.users().messages().get().execute.return_value = {
            'id': '1',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Integration Test'},
                    {'name': 'From', 'value': 'test@domain.com'},
                    {'name': 'To', 'value': 'b@c.com'},
                    {'name': 'Date', 'value': 'Wed, 26 Jun 2024 10:30:00 +0000'}
                ],
                'body': {'data': 'Ym9keQ=='}  # base64 for 'body'
            }
        }
        fetch_emails.fetch_emails(mock_service, max_results=1)
        # Check DB
        conn = sqlite3.connect(self.DB_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM Emails')
        rows = c.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], 'test@domain.com')
        conn.close()

    @patch('src.process_emails.authenticate_gmail')
    def test_process_emails_rule_action(self, mock_auth):
        # Insert a test email into DB
        conn = sqlite3.connect(self.DB_NAME)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS Emails (
            gmail_id TEXT PRIMARY KEY,
            sender TEXT,
            recipient TEXT,
            subject TEXT,
            message TEXT,
            date TEXT
        )''')
        c.execute('''INSERT INTO Emails (gmail_id, sender, recipient, subject, message, date) VALUES (?, ?, ?, ?, ?, ?)''',
                  ('1', 'test@domain.com', 'b@c.com', 'Integration Test', 'body', '26/06/2024 16:00:00'))
        conn.commit()
        conn.close()
        # Mock Gmail API service
        mock_service = MagicMock()
        mock_auth.return_value = mock_service
        # Patch Gmail API mark as read
        mock_service.users().messages().modify.return_value.execute.return_value = {}
        # Patch fetch_emails_from_db to use our DB
        with patch('process_emails.fetch_emails_from_db', wraps=process_emails.fetch_emails_from_db):
            process_emails.process_emails()
        # Check that mark as read was called
        self.assertTrue(mock_service.users().messages().modify.called)

if __name__ == '__main__':
    unittest.main()

