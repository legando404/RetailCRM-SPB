from fastapi import FastAPI, Request, Body
from pydantic import BaseModel
from time import time
import httpx
import asyncio
import json
import imaplib
import email
from imap_tools import MailBox, AND
from email.header import decode_header
import base64
import re
import os
import retailcrm
import yadisk
import aiofiles
import http.client 
from dotenv import load_dotenv

load_dotenv()
#res = #conn.getresponse() data = res.read() print()

app = FastAPI()
#url = 'https://mdevelopeur.retailcrm.ru/api/v5/'
url = os.getenv("URL")#'https://laminat77.retailcrm.ru'
site = os.getenv('site')#= 'novers-spb'
apikey = os.getenv('key') #'vikuHSdIKilFPMr0oyj5LpemwHvEPjVw'
#apikey = 'nHY0H7zd7UWwcEiwN0EbwhXz2eGY9o9G'
retail_client = retailcrm.v5(url, apikey)
#headers = {'X-API-KEY' : apikey}
conn = http.client.HTTPSConnection('laminat77.retailcrm.ru')
headers = { 'X-API-KEY': apikey, 'Content-Type': 'image/jpeg' }  
#password = "zrAUqnFWgD14Ygkq13VK"
#username = "kworktestbox@mail.ru"
password = os.getenv('password')  #"r4ZuvyWydYMktHuTn3uJ"
username = os.getenv('user')#"novers495@mail.ru"
imap_server = os.getenv('imap')#"imap.mail.ru"

async def upload_file(client, file, order):
    print(file.filename, file.content_disposition)
    try:
        response = await client.post(url + "/api/v5/files/upload", data = file.payload, headers = headers)
        id = response.json()["file"]["id"]
        filename = ''.join(re.findall(r"\w+| |\.", file.filename))
        data = { 'id': id, 'filename': file.filename, 'attachment': [{'order':{'id': order}}]}
        response = retail_client.files_edit(data)
        print(response.get_response())
    except Exception as e:
                print('exception: ', e)

async def main(client):
    messages = await get_mail(username, password, imap_server)
    for msg in messages : 
        for a in msg["attachments"]:
            print(a.filename)
        #for a in msg["attachments"]: 
            #files = {'file': a.payload}
            #try:                       
                #conn.request("POST", "/api/v5/files/upload", a.payload, headers)
                #file = conn.getresponse().read().decode("utf-8")
                #file = await client.post(url + '/api/v5/files/upload', payload=a.payload, headers=headers)
            #except Exception as e:
                #print('exception: ', e)
            #print(file.content, file.json()["file"]["id"])
        response = await post_order(retail_client, msg["first_name"], msg["last_name"], msg["email"], msg["subject"], msg["text"], msg["html"], msg["attachments"])
        order = response.get_response()["id"]
        for a in msg["attachments"]: 
            if a.content_disposition == 'attachment':
                await upload_file(client, a, order)
        return response    

async def post_order(client, first_name, last_name, email, subject, text, html, attachments):
    print('posting...')
    try:
        filter = {'email': email}
        customers = client.customers(filter).get_response().get("customers", [])
    except Exception as e:
        print('Exception in customer fetch:', e)
        traceback.print_exc()
        return None

    try:
        print('posting.... ', customers)
        order = {
            'customerComment': text,
            'status': 'novoe-pismo',
            'orderMethod': 'e-mail',
            'lastName': last_name,
            'firstName': first_name,
            'email': email,
            'customFields': {
                'tema_pisma1': subject,
                'tekst_pisma': text
            }
        }

        if customers:
            order["customer"] = {'id': customers[0]["id"]}

        print("[DEBUG] Creating order with:", json.dumps(order, indent=2, ensure_ascii=False))
        print(f"[DEBUG] site: {site}")

        result = client.order_create(order, site)
        print('result:', result.get_response())
        return result

    except Exception as e:
        print('Exception in order_create:', e)
        traceback.print_exc()
        return None


async def get_mail(username, password, imap_server, folder='Novers СПБ', limit=10):
    array = []
    print('connecting to imap server...')

    with MailBox(imap_server).login(username, password, initial_folder=folder) as mailbox:
        print('fetching unread...')
        for msg in mailbox.fetch(AND(seen=False), limit=limit):
            attachments = [a for a in msg.attachments]
            print(f"{len(attachments)} attachments in message from {msg.from_}")

            # Распознаём имя
            match = re.search(r'(.*) <' + re.escape(msg.from_) + '>', msg.from_values.full or '')
            if match:
                parts = match.group(1).split()
                lastName = parts[-1]
                firstName = ' '.join(parts[:-1])
            else:
                firstName = ''
                lastName = msg.from_

            data = {
                "email": msg.from_,
                "first_name": firstName,
                "last_name": lastName,
                "subject": msg.subject,
                "text": msg.text,
                "html": msg.html,
                "attachments": attachments,
            }
            array.append(data)

            # Отметить как прочитанное
            mailbox.flag(msg.uid, flags=[r'\Seen'], action='add')

    return array




async def task():
    async with httpx.AsyncClient() as client:
        tasks = [main(client) for i in range(1)]
        result = await asyncio.gather(*tasks)
        return result

from fastapi.responses import JSONResponse
import traceback

@app.get('/api')
async def api_handler():
    try:
        print("➡️ Вход в /api")
        output = await task()
        return output
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
