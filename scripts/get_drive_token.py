"""One-time helper: sign in with your Google account and print a Drive refresh token.

Usage: python scripts/get_drive_token.py path/to/oauth_client.json
(the "Desktop app" OAuth client JSON downloaded from Google Cloud Console)
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    sys.argv[1], scopes=["https://www.googleapis.com/auth/drive"]
)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
print("\nAdd this to your Streamlit secrets:\n")
print("[drive_oauth]")
print(f'client_id = "{creds.client_id}"')
print(f'client_secret = "{creds.client_secret}"')
print(f'refresh_token = "{creds.refresh_token}"')
