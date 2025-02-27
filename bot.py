import json
import os
import asyncio
import aiohttp
import base64
from telethon import TelegramClient, events
from telethon.tl import functions

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session_base64 = os.getenv("SESSION_BASE64")
DB_FILE = "users.json"

if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        users_data = json.load(f)
else:
    users_data = {"gpt_enabled": False}

session_bytes = base64.b64decode(session_base64)
with open("session.session", "wb") as session_file:
    session_file.write(session_bytes)

client = TelegramClient("session.session", api_id, api_hash)

async def save_data():
    with open(DB_FILE, "w") as f:
        json.dump(users_data, f, indent=4)

async def send_welcome(event, user_id):
    attempts_left = max(0, 3 - users_data[user_id]["messages_count"])
    message = await event.respond(
        f"🚨 **Automated Security System - NotCyberSec** 🚨\n\n"
        f"⚠️ **@imoslo is currently unavailable.**\n"
        f"📢 Please avoid sending too many messages to prevent restrictions.\n"
        f"✅ Your request has been logged, and you will be responded to soon.\n"
        f"🔄 Attempts left before restriction: **{attempts_left}**\n\n"
        f"🔒 *This protection is powered by NotCyberSec to ensure a safer communication experience.*",
        parse_mode="markdown"
    )
    users_data[user_id]["welcome_message_id"] = message.id
    await save_data()

async def delete_message_after_delay(event, delay=2):
    await asyncio.sleep(delay)
    await event.delete()

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    sender = await event.get_sender()
    if sender is None or not hasattr(sender, "id"):
        return

    user_id = str(sender.id)
    if event.is_group or event.is_channel:
        return

    if user_id not in users_data:
        users_data[user_id] = {"username": sender.username or "Unknown", "allowed": False, "muted": False, "messages_count": 0, "welcome_message_id": None}
        await send_welcome(event, user_id)

    if users_data[user_id]["muted"]:
        await event.delete()
        return

    users_data[user_id]["messages_count"] += 1
    if users_data[user_id]["messages_count"] <= 2 and not users_data[user_id]["allowed"]:
        old_message_id = users_data[user_id].get("welcome_message_id")
        if old_message_id:
            try:
                await client.delete_messages(event.chat_id, old_message_id)
            except Exception:
                pass  
        await send_welcome(event, user_id)

    elif users_data[user_id]["messages_count"] == 3 and not users_data[user_id]["allowed"]:
        await send_welcome(event, user_id)  

    elif users_data[user_id]["messages_count"] > 3 and not users_data[user_id]["allowed"]:
        await event.delete()
    
    await save_data()

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.o$"))
async def allow_user(event):
    sender = await event.get_chat()
    if sender is None or not hasattr(sender, "id"):
        return

    user_id = str(sender.id)
    if user_id in users_data:
        users_data[user_id]["allowed"] = True
        users_data[user_id]["messages_count"] = 0
        await event.respond("✅ You are now allowed to send messages freely.")
        await save_data()
        await delete_message_after_delay(event)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.mute$"))
async def mute_user(event):
    sender = await event.get_chat()
    if sender is None or not hasattr(sender, "id"):
        return

    user_id = str(sender.id)
    if user_id in users_data:
        users_data[user_id]["muted"] = True
        message = await event.respond("🔇 **You are now muted. Your messages will be deleted immediately.**", parse_mode="markdown")
        await asyncio.sleep(2)
        await message.delete()
        await save_data()
        await delete_message_after_delay(event)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.unm$"))
async def unmute_user(event):
    sender = await event.get_chat()
    if sender is None or not hasattr(sender, "id"):
        return

    user_id = str(sender.id)
    if user_id in users_data:
        users_data[user_id]["muted"] = False
        message = await event.respond("🔊 **You are now unmuted. You can send messages again.**", parse_mode="markdown")
        await asyncio.sleep(2)
        await message.delete()
        await save_data()
        await delete_message_after_delay(event)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ogpt$"))
async def enable_gpt(event):
    users_data["gpt_enabled"] = True
    await event.respond("✅ **GPT mode enabled. Users can now use /gpt command.**", parse_mode="markdown")
    await save_data()
    await delete_message_after_delay(event)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ngpt$"))
async def disable_gpt(event):
    users_data["gpt_enabled"] = False
    await event.respond("❌ **GPT mode disabled. Users can no longer use /gpt command.**", parse_mode="markdown")
    await save_data()
    await delete_message_after_delay(event)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.dms$"))
async def delete_my_messages(event):
    chat = await event.get_chat()
    async for message in client.iter_messages(chat, from_user="me"):
        try:
            await message.delete()
        except Exception as e:
            print(f"Failed to delete message: {e}")

    confirmation = await event.respond("✅ **All your messages in this chat have been deleted.**", parse_mode="markdown")
    await asyncio.sleep(2)
    await confirmation.delete()

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.inf$"))
async def user_info(event):
    if not event.is_reply:
        await event.respond("❌ **Please reply to a message to use this command.**", parse_mode="markdown")
        return

    replied_message = await event.get_reply_message()
    user = await replied_message.get_sender()

    if user is None:
        await event.respond("❌ **Unable to retrieve user information.**", parse_mode="markdown")
        return

    user_id = user.id
    username = user.username if user.username else "None"
    first_name = user.first_name if user.first_name else "None"
    last_name = user.last_name if user.last_name else "None"
    full_name = f"{first_name} {last_name}".strip()
    is_bot = user.bot
    is_restricted = user.restricted
    is_scam = user.scam
    is_verified = user.verified

    info_message = (
        f"👤 **User Information**\n\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"👤 **Username:** @{username}\n"
        f"📛 **Name:** {full_name}\n"
        f"🤖 **Is Bot:** {is_bot}\n"
        f"🔒 **Is Restricted:** {is_restricted}\n"
        f"⚠️ **Is Scam:** {is_scam}\n"
        f"✅ **Is Verified:** {is_verified}\n"
    )

    await event.respond(info_message, parse_mode="markdown")
    await delete_message_after_delay(event)

async def main():
    await client.start()
    print("🚀 Bot is now running and listening for messages...")
    await client.run_until_disconnected()

asyncio.run(main())
