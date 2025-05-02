# 🚨 PSG Watcher Script for Railway
# Detects Gmail message, notifies via WhatsApp (Twilio), and triggers Render webhook

import os
import time
import base64
import requests
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from twilio.rest import Client

# --- Gmail Setup ---
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
KEYWORDS = ['Abonnement', 'Ouverture des ventes']
SENDER = 'newsletter@psg.fr'

# --- Twilio Setup ---
TWILIO_SID = os.environ['TWILIO_SID']
TWILIO_TOKEN = os.environ['TWILIO_TOKEN']
TWILIO_FROM = 'whatsapp:+14155238886'  # Twilio sandbox
TWILIO_TO = 'whatsapp:+33630299726'  # Quentin

# --- Webhook to Render (starts Puppeteer) ---
RENDER_WEBHOOK = os.environ['RENDER_WEBHOOK_URL']

def get_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
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

        if any(k in subject for k in KEYWORDS) and SENDER in sender:
            print(f"🎯 Mail détecté : {subject}")
            parts = msg_data['payload'].get('parts', [])
            for part in parts:
                if 'data' in part['body']:
                    decoded_data = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    soup = BeautifulSoup(decoded_data, 'html.parser')
                    for link in soup.find_all('a', href=True):
                        if 'billetterie.psg.fr' in link['href']:
                            url = link['href']
                            print(f"🔗 Lien détecté : {url}")

                            # Envoi WhatsApp + déclenchement webhook
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
