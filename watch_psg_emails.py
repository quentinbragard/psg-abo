# watch_psg_emails.py — script Railway complet avec décodage base64 pour token.json et credentials.json

import os
import time
import base64
import requests
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from twilio.rest import Client
import dotenv

dotenv.load_dotenv()    

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
KEYWORDS = ['Abonnement', 'Ouverture des ventes']
SENDER = 'newsletter@psg.fr'

# --- Decode credentials.json from base64 ---
if 'CREDENTIALS_JSON_BASE64' in os.environ:
    decoded = base64.b64decode(os.environ['CREDENTIALS_JSON_BASE64']).decode('utf-8')
    with open('credentials.json', 'w') as f:
        f.write(decoded)

# --- Decode token.json from base64 ---
if 'TOKEN_JSON_BASE64' in os.environ:
    decoded = base64.b64decode(os.environ['TOKEN_JSON_BASE64']).decode('utf-8')
    with open('token.json', 'w') as f:
        f.write(decoded)

# --- Twilio Setup ---
TWILIO_SID = os.environ['TWILIO_SID']
TWILIO_TOKEN = os.environ['TWILIO_TOKEN']
TWILIO_FROM = 'whatsapp:+14155238886'
TWILIO_TO = 'whatsapp:+33630299726'
RENDER_WEBHOOK = os.environ['RENDER_WEBHOOK_URL']

def get_service():
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    return build('gmail', 'v1', credentials=creds)

def send_whatsapp(body):
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    message = client.messages.create(
        from_=TWILIO_FROM,
        to=TWILIO_TO,
        body=body
    )
    print("✅ WhatsApp message sent")

def check_latest_emails(service):
    results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=5).execute()
    messages = results.get('messages', [])

    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        headers = msg_data['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '')

        if any(k in subject for k in KEYWORDS):
            print(f"🎯 Mail détecté : {subject}")
            send_whatsapp(f"📣 PSG : ouverture détectée !")
            parts = msg_data['payload'].get('parts', [])
            for part in parts:
                if 'data' in part['body']:
                    decoded_data = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    soup = BeautifulSoup(decoded_data, 'html.parser')
                    for link in soup.find_all('a', href=True):
                        if 't.newsletter.psg.fr' in link['href']:
                            url = link['href']
                            print(f"🔗 Lien détecté : {url}")
                            send_whatsapp(f"📣 PSG : ouverture détectée ! File d'attente en cours...\n{url}")
                            requests.post(RENDER_WEBHOOK, json={"url": url})
                            return True
    return False

if __name__ == '__main__':
    service = get_service()
    print("🕵️ Surveillance Gmail active...")
    while True:
        try:
            if check_latest_emails(service):
                print("✅ Action complète. Arrêt du script.")
                break
        except Exception as e:
            print(f"⚠️ Erreur : {e}")
        time.sleep(10)
