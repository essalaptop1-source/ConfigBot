import discord
from discord import app_commands
import os
import asyncio
from flask import Flask
from threading import Thread

# 1. Initialize Flask Web Listener for Render
app = Flask('')

@app.route('/')
def home():
    return "Operational Status: Active"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. Configure Client Subclass 
class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Starts the web server worker cleanly
        server_thread = Thread(target=run_web_server)
        server_thread.start()

client = MyClient()

# HARDCODED CORRECT DISCORD INVITE LINK
LIVE_LINK = "https://discord.gg/dt248N6Be"

# --- COMMAND 1: FLOOD ---
@client.tree.command(name="flood", description="Sends the baseline heading layout configuration.")
@app_commands.allowed_installs(guilds=False, users=True)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
async def flood(interaction: discord.Interaction):
    # CRITICAL FIX: Give immediate system feedback to prevent the 3-second timeout freeze
    await interaction.response.defer(ephemeral=False)
    
    payload = (
        f"# **POWER OF CONFIG2 {LIVE_LINK}**\n"
        f"# **POWER OF CONFIG2 {LIVE_LINK}**\n"
        f"# **POWER OF CONFIG2 {LIVE_LINK}**\n"
        f"# **POWER OF CONFIG2 {LIVE_LINK}**"
    )
    try:
        await interaction.followup.send(content=payload)
    except Exception as e:
        print(f"Error firing /flood: {e}")

# --- COMMAND 2: BURST ---
@client.tree.command(name="burst", description="Fires multiple sequential text waves.")
@app_commands.allowed_installs(guilds=False, users=True)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
async def burst(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    payload = (
        f"# **POWER OF CONFIG2 {LIVE_LINK}**\n"
        f"# **POWER OF CONFIG2 {LIVE_LINK}**"
    )
    
    # Safely fires 5 separate payloads using followups to fix the single-send limitation
    for i in range(5):
        try:
            await interaction.followup.send(content=f"**[Wave {i+1}/5]**\n{payload}")
            await asyncio.sleep(2.0)  # Safe delay to prevent a hard 429 gateway lock
        except Exception as e:
            print(f"Burst interrupted: {e}")
            break

# --- COMMAND 3: EXTREME ---
@client.tree.command(name="extreme", description="Drops an ultra-dense maximum character layout footprint.")
@app_commands.allowed_installs(guilds=False, users=True)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
async def extreme(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    single_line = f"# **POWER OF CONFIG2 {LIVE_LINK}**\n"
    massive_payload = single_line * 15  # Spams maximum allowable screen real estate
    
    try:
        await interaction.followup.send(content=massive_payload)
    except Exception as e:
        print(f"Error firing /extreme: {e}")

# --- GLOBAL SYNCHRONIZATION OVERRIDE ---
@client.event
async def on_ready():
    print(f"Authenticated as {client.user.name}")
    try:
        print("Forcing clean global command sync down to Discord API...")
        await client.tree.sync()
        print("Sync operation successful! Commands ready across accounts.")
    except Exception as e:
        print(f"Sync failed: {e}")

if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("DISCORD_TOKEN")
    client.run(BOT_TOKEN)
