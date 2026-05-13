import discord
from discord import app_commands
import os
import asyncio
from flask import Flask
from threading import Thread

# 1. Setup Flask Web Server to satisfy Render's health checks
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. Configure Client with Hard-Sync Capabilities
class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        print("Clearing old command caches...")
        # Wipes previous global cache to prevent CommandNotFound sync errors
        self.tree.clear(guild=None) 
        print("Registering and syncing new global multi-commands...")
        await self.tree.sync()
        print("All user-installable commands synced successfully!")

client = MyClient()

# Shared settings variable
YOUR_DISCORD_LINK = "https://discord.gg/dt248N6Be"

# --- COMMAND 1: STANDARD FLOOD ---
@client.tree.command(name="flood", description="Delivers the default configuration payload.")
@app_commands.allowed_installs(guilds=False, users=True)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
async def flood(interaction: discord.Interaction):
    await interaction.response.send_message("⚠️ **Initializing Payload Delivery...**")
    payload = (
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**\n"
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**\n"
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**\n"
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**"
    )
    try:
        await interaction.followup.send(content=payload)
    except Exception as e:
        print(f"Failed to execute /flood: {e}")

# --- COMMAND 2: MULTI-BURST ---
# Resolves the "only sends message one time" limit by firing multiple sequential followups before the session token expires
@client.tree.command(name="burst", description="Delivers multiple sequential text payload blocks.")
@app_commands.allowed_installs(guilds=False, users=True)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
async def burst(interaction: discord.Interaction):
    await interaction.response.send_message("🚀 **Deploying multi-burst matrix...**")
    payload = (
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**\n"
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**"
    )
    
    # Sends 5 separate blocks safely spaced apart to dodge Discord's aggressive HTTP 429 spam filter
    for i in range(5):
        try:
            await interaction.followup.send(content=f"**[Stream Wave {i+1}/5]**\n{payload}")
            await asyncio.sleep(1.5) 
        except discord.errors.Forbidden:
            print("Dropped wave: Channel admin has restricted external app output.")
            break
        except Exception as e:
            print(f"Error during burst drop: {e}")
            break

# --- COMMAND 3: EXTREME PAYLOAD ---
# Generates a massive character-capped layout block 
@client.tree.command(name="extreme", description="Delivers an ultra-dense maximum character block.")
@app_commands.allowed_installs(guilds=False, users=True)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
async def extreme(interaction: discord.Interaction):
    await interaction.response.send_message("☣️ **Compiling maximum density configuration matrix...**")
    
    # Creates a repeated loop string right up against Discord's message size limit
    single_line = f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**\n"
    massive_payload = single_line * 15 
    
    try:
        await interaction.followup.send(content=massive_payload)
    except Exception as e:
        print(f"Failed to execute /extreme: {e}")

# --- COMMAND 4: HELP MENU ---
@client.tree.command(name="confighelp", description="Displays all accessible user application commands.")
@app_commands.allowed_installs(guilds=False, users=True)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
async def confighelp(interaction: discord.Interaction):
    help_text = (
        "🛠️ **Config2 User-App Command Manifest:**\n"
        "`/flood` - Sends the baseline layout configuration block.\n"
        "`/burst` - Fires off 5 sequential text waves tracking session parameters.\n"
        "`/extreme` - Drops a maximum character footprint data stream.\n"
        "`/confighelp` - Opens this diagnostic module guide."
    )
    await interaction.response.send_message(content=help_text, ephemeral=True)

# 4. Execution Runtime Setup
if __name__ == "__main__":
    server_thread = Thread(target=run_web_server)
    server_thread.start()

    BOT_TOKEN = os.environ.get("DISCORD_TOKEN")
    client.run(BOT_TOKEN)
