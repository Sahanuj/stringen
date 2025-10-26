from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, SessionPasswordNeededError
import asyncio
import os

async def create_session(phone: str, code: str, password: str = None) -> tuple[str, bool]:
    try:
        api_id = int(os.getenv("API_ID"))
        api_hash = os.getenv("API_HASH")
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        await client.send_code_request(phone)
        await client.sign_in(phone, code, password=password)
        session_string = client.session.save()
        await client.disconnect()
        return session_string, False
    except SessionPasswordNeededError:
        return "2FA required", True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        return await create_session(phone, code, password)
    except Exception as e:
        return f"Error: {str(e)}", False
