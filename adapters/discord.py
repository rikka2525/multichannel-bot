import asyncio
import logging
from models import IncomingMessage

def normalize(message, allowed_users, allowed_channels):
    if message.author.bot or str(message.author.id) not in allowed_users or str(message.channel.id) not in allowed_channels:
        return None
    return IncomingMessage(str(message.id), str(message.author.id), message.content)

def run(core, token, allowed_users, allowed_channels):
    import discord
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print("Discord ready: Gateway connected", flush=True)

    @client.event
    async def on_message(message):
        incoming = normalize(message, allowed_users, allowed_channels)
        if incoming is None:
            return
        print("Discord received: allowed message", flush=True)
        loop = asyncio.get_running_loop()
        class Sender:
            def send_text(self, recipient, text):
                future = asyncio.run_coroutine_threadsafe(
                    message.channel.send(text, allowed_mentions=discord.AllowedMentions.none()), loop)
                future.result()
        try:
            reply = await asyncio.to_thread(core.handle, incoming, Sender(), channel="discord", scope=str(message.channel.id))
            print("Discord complete: reply sent and DB committed" if reply is not None
                  else "Discord skipped: duplicate message", flush=True)
        except Exception as error:
            logging.error("Discord processing failed (%s); delivery or DB commit incomplete", type(error).__name__)

    client.run(token, log_handler=None)
