import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import base64

import src.fetch_emails as fetch_emails

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

class TestFetchEmails(unittest.TestCase):
    def setUp(self):
        self.db_name = 'TestEmailDatabase.db'
        self.table_name = 'Emails'
        fetch_emails.DB_NAME = self.db_name
        fetch_emails.TABLE_NAME = self.table_name
        # Remove test DB if exists
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def tearDown(self):
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def test_log_error(self):
        log_file = 'test_fetch_emails.log'
        if os.path.exists(log_file):
            os.remove(log_file)
        fetch_emails.LOG_FILE = log_file
        fetch_emails.log_error('Test error message')
        with open(log_file, 'r') as f:
            content = f.read()
        self.assertIn('Test error message', content)
        os.remove(log_file)

    def test_setup_database_creates_table(self):
        conn, c = fetch_emails.setup_database()
        c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_name}'")
        self.assertIsNotNone(c.fetchone())
        conn.close()

    def test_format_email_date_valid(self):
        date_str = 'Wed, 26 Jun 2024 10:30:00 +0000'
        formatted = fetch_emails.format_email_date(date_str)
        self.assertEqual(formatted, '26/06/2024 16:00:00')

    def test_format_email_date_invalid(self):
        date_str = 'invalid-date-string'
        formatted = fetch_emails.format_email_date(date_str)
        self.assertEqual(formatted, date_str)

    def test_extract_message_body_single(self):
        payload = {'body': {'data': base64.urlsafe_b64encode(b'hello').decode('utf-8')}}
        result = fetch_emails.extract_message_body(payload)
        self.assertEqual(result, 'hello')

    def test_extract_message_body_multipart(self):
        payload = {
            'parts': [
                {'mimeType': 'text/plain', 'body': {'data': base64.urlsafe_b64encode(b'world').decode('utf-8')}}
            ]
        }
        result = fetch_emails.extract_message_body(payload)
        self.assertEqual(result, 'world')

    @patch('src.fetch_emails.authenticate_gmail')
    @patch('src.fetch_emails.setup_database')
    def test_fetch_emails_handles_api(self, mock_setup_db, mock_auth):
        # Setup mocks
        mock_service = MagicMock()
        mock_auth.return_value = mock_service
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_setup_db.return_value = (mock_conn, mock_cursor)
        mock_service.users().messages().list().execute.return_value = {
            'messages': [{'id': '1'}]
        }
        mock_service.users().messages().get().execute.return_value = {
            'id': '1',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Test'},
                    {'name': 'From', 'value': 'a@b.com'},
                    {'name': 'To', 'value': 'b@c.com'},
                    {'name': 'Date', 'value': 'Wed, 26 Jun 2024 10:30:00 +0000'}
                ],
                'body': {'data': base64.urlsafe_b64encode(b'body').decode('utf-8')}
            }
        }
        fetch_emails.fetch_emails(mock_service, max_results=1)
        self.assertTrue(mock_cursor.execute.called)
        self.assertTrue(mock_conn.commit.called)

if __name__ == '__main__':
    unittest.main()

