import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
import sqlite3
import re
from datetime import datetime, timedelta
import os

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== DATABASE ==========
conn = sqlite3.connect("security.db")
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS config (
    guild_id INTEGER PRIMARY KEY,
    automod INTEGER DEFAULT 0,
    antinuke INTEGER DEFAULT 0,
    trap_channel INTEGER,
    log_channel INTEGER,
    whitelist_role INTEGER
)''')

c.execute('''CREATE TABLE IF NOT EXISTS warnings (
    user_id INTEGER,
    guild_id INTEGER,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, guild_id)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS whitelist (
    user_id INTEGER,
    guild_id INTEGER,
    PRIMARY KEY (user_id, guild_id)
)''')

conn.commit()

# ========== BAD WORDS LIST ==========
bad_words = [
    # Direct insults
    "fuck", "shit", "asshole", "bitch", "damn", "hell", "stupid", "idiot", "dumb", "retard",
    "cunt", "dick", "pussy", "cock", "whore", "slut", "bastard", "twat", "fag", "faggot",
    # Racial slurs
    "nigger", "nigga", "chink", "spic", "kike", "gook", "wetback", "cracker", "honky",
    # Bypass attempts
    "f.u.c.k", "f u c k", "f*ck", "f**k", "f@ck", "fuuck",
    "s.h.i.t", "s h i t", "s*it", "sh*t", "sh!t",
    "b.i.t.c.h", "b i t c h", "b*tch", "b!tch", "b1tch",
    "a.s.s.h.o.l.e", "a s s h o l e", "assh*le", "a55hole",
    "c.u.n.t", "c u n t", "c*nt",
    "d.i.c.k", "d i c k", "d*ck", "d1ck",
    "p.u.s.s.y", "p u s s y", "p*ssy",
    # Numbers for letters
    "b1tch", "sh1t", "c0ck", "d1ck", "f4g", "n1gg3r", "4ss", "5hit",
    # Combined
    "motherfucker", "fuckface", "shithead", "dickhead", "assface",
    "rape", "pedo", "pedophile", "kys"
]

# ========== CONFIG STORAGE ==========
automod_enabled = {}
antinuke_enabled = {}
trap_channel = {}
log_channel = {}
join_tracker = {}
message_counter = {}

# ========== HELPER FUNCTIONS ==========
async def add_warning(user_id, guild_id):
    c.execute("INSERT INTO warnings (user_id, guild_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, guild_id) DO UPDATE SET count = count + 1", (user_id, guild_id))
    conn.commit()

def get_warning_count(user_id, guild_id):
    c.execute("SELECT count FROM warnings WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
    result = c.fetchone()
    return result[0] if result else 0

async def log_action(guild_id, message):
    if log_channel.get(guild_id):
        channel = bot.get_channel(log_channel[guild_id])
        if channel:
            embed = discord.Embed(title="🛡️ Security Log", description=message, color=discord.Color.red(), timestamp=datetime.now())
            await channel.send(embed=embed)

def contains_bad_words(text):
    text_lower = text.lower()
    for word in bad_words:
        if word in text_lower:
            return True
    return False

async def check_spam(message):
    guild_id = message.guild.id
    user_id = message.author.id
    
    key = f"{guild_id}_{user_id}"
    if key not in message_counter:
        message_counter[key] = []
    
    message_counter[key].append(datetime.now())
    message_counter[key] = [t for t in message_counter[key] if (datetime.now() - t).seconds < 5]
    
    if len(message_counter[key]) > 5:
        await message.delete()
        await message.channel.send(f"{message.author.mention} Stop spamming!", delete_after=3)
        await add_warning(user_id, guild_id)
        
        if get_warning_count(user_id, guild_id) >= 3:
            await message.author.timeout(timedelta(minutes=10))
            await log_action(guild_id, f"⏰ Timed out {message.author.mention} for spam (3 warnings)")

# ========== EVENTS ==========
@bot.event
async def on_ready():
    print(f"✅ Security Bot is online as {bot.user}")
    c.execute("SELECT guild_id, automod, antinuke, trap_channel, log_channel FROM config")
    for row in c.fetchall():
        guild_id, auto, anti, trap, log = row
        automod_enabled[guild_id] = auto
        antinuke_enabled[guild_id] = anti
        trap_channel[guild_id] = trap
        log_channel[guild_id] = log
    print(f"Loaded settings for {len(automod_enabled)} servers")

@bot.event
async def on_member_join(member):
    guild_id = member.guild.id
    
    if guild_id not in join_tracker:
        join_tracker[guild_id] = []
    
    join_tracker[guild_id].append(datetime.now())
    join_tracker[guild_id] = [t for t in join_tracker[guild_id] if (datetime.now() - t).seconds < 30]
    
    if len(join_tracker[guild_id]) > 5 and antinuke_enabled.get(guild_id, 0) == 1:
        await member.guild.edit(verification_level=discord.VerificationLevel.high)
        await log_action(guild_id, "⚠️ **RAID DETECTED!** Server verification increased to HIGH")
        await member.ban(reason="Raid detection - mass join")
        await log_action(guild_id, f"🔨 Banned {member.name} (raid detection)")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    guild_id = message.guild.id
    
    # Trap channel
    if trap_channel.get(guild_id) == message.channel.id:
        await message.author.ban(reason="Typed in trap channel")
        await log_action(guild_id, f"🔨 **BANNED** {message.author.mention} (trap channel)")
        return
    
    # Auto-mod
    if automod_enabled.get(guild_id, 0) == 1:
        await check_spam(message)
        
        if contains_bad_words(message.content):
            await message.delete()
            await message.channel.send(f"{message.author.mention} No bad words!", delete_after=3)
            await add_warning(message.author.id, guild_id)
    
    # Anti-nuke
    if antinuke_enabled.get(guild_id, 0) == 1:
        if message.content.lower().startswith(("!purge", "!clear", "!massban")):
            if not message.author.guild_permissions.administrator:
                await message.delete()
                await message.author.timeout(timedelta(minutes=5), reason="Suspected nuke attempt")
                await log_action(guild_id, f"⚠️ **Anti-Nuke:** {message.author.mention} attempted mass deletion, timed out")

    await bot.process_commands(message)

# ========== SECURITY PANEL ==========
class SecurityPanel(View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    
    @discord.ui.button(label="🛡️ Auto-Mod (DISABLED)", style=discord.ButtonStyle.primary, row=0)
    async def automod_btn(self, interaction: discord.Interaction, button: Button):
        current = automod_enabled.get(self.guild_id, 0)
        new = 1 if current == 0 else 0
        automod_enabled[self.guild_id] = new
        c.execute("INSERT OR REPLACE INTO config (guild_id, automod) VALUES (?, ?)", (self.guild_id, new))
        conn.commit()
        status = "ENABLED" if new == 1 else "DISABLED"
        button.label = f"🛡️ Auto-Mod ({status})"
        await interaction.response.edit_message(view=self)
        await log_action(self.guild_id, f"Auto-Mod {status} by {interaction.user.mention}")
    
    @discord.ui.button(label="🚨 Anti-Nuke (DISABLED)", style=discord.ButtonStyle.danger, row=0)
    async def antinuke_btn(self, interaction: discord.Interaction, button: Button):
        current = antinuke_enabled.get(self.guild_id, 0)
        new = 1 if current == 0 else 0
        antinuke_enabled[self.guild_id] = new
        c.execute("INSERT OR REPLACE INTO config (guild_id, antinuke) VALUES (?, ?)", (self.guild_id, new))
        conn.commit()
        status = "ENABLED" if new == 1 else "DISABLED"
        button.label = f"🚨 Anti-Nuke ({status})"
        await interaction.response.edit_message(view=self)
        await log_action(self.guild_id, f"Anti-Nuke {status} by {interaction.user.mention}")
    
    @discord.ui.button(label="🚫 Set Trap Channel", style=discord.ButtonStyle.secondary, row=1)
    async def trap_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("**Set Trap Channel**\n\nType `!settrap #channel`", ephemeral=True)
    
    @discord.ui.button(label="📋 Set Log Channel", style=discord.ButtonStyle.secondary, row=1)
    async def log_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("**Set Log Channel**\n\nType `!setlog #channel`", ephemeral=True)

# ========== COMMANDS ==========
@bot.command()
@commands.has_permissions(administrator=True)
async def security_panel(ctx):
    """!security_panel - Show security control panel"""
    embed = discord.Embed(title="🛡️ Security Control Panel", description="Click buttons to enable/disable features", color=discord.Color.blue())
    embed.add_field(name="Auto-Mod", value="Spam protection + bad word filter", inline=False)
    embed.add_field(name="Anti-Nuke", value="Raid detection + mass deletion protection", inline=False)
    embed.add_field(name="Trap Channel", value="Instant ban anyone who types", inline=False)
    view = SecurityPanel(ctx.guild.id)
    await ctx.send(embed=embed, view=view)

@bot.command()
@commands.has_permissions(administrator=True)
async def settrap(ctx, channel: discord.TextChannel):
    """!settrap #channel - Set trap channel"""
    c.execute("INSERT OR REPLACE INTO config (guild_id, trap_channel) VALUES (?, ?)", (ctx.guild.id, channel.id))
    conn.commit()
    trap_channel[ctx.guild.id] = channel.id
    await ctx.send(f"✅ Trap channel set to {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setlog(ctx, channel: discord.TextChannel):
    """!setlog #channel - Set log channel"""
    c.execute("INSERT OR REPLACE INTO config (guild_id, log_channel) VALUES (?, ?)", (ctx.guild.id, channel.id))
    conn.commit()
    log_channel[ctx.guild.id] = channel.id
    await ctx.send(f"✅ Log channel set to {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def security_status(ctx):
    """!security_status - Show current settings"""
    auto = automod_enabled.get(ctx.guild.id, 0)
    anti = antinuke_enabled.get(ctx.guild.id, 0)
    trap = trap_channel.get(ctx.guild.id, "Not set")
    logc = log_channel.get(ctx.guild.id, "Not set")
    
    embed = discord.Embed(title="🛡️ Security Status", color=discord.Color.blue())
    embed.add_field(name="Auto-Mod", value="✅ ENABLED" if auto else "❌ DISABLED", inline=True)
    embed.add_field(name="Anti-Nuke", value="✅ ENABLED" if anti else "❌ DISABLED", inline=True)
    embed.add_field(name="Trap Channel", value=f"<#{trap}>" if trap != "Not set" else "❌ Not set", inline=True)
    embed.add_field(name="Log Channel", value=f"<#{logc}>" if logc != "Not set" else "❌ Not set", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def security_help(ctx):
    """!security_help - Show commands"""
    embed = discord.Embed(title="🛡️ Security Bot Commands", color=discord.Color.blue())
    embed.add_field(name="!security_panel", value="Open control panel", inline=False)
    embed.add_field(name="!settrap #channel", value="Set trap channel", inline=False)
    embed.add_field(name="!setlog #channel", value="Set log channel", inline=False)
    embed.add_field(name="!security_status", value="Show current settings", inline=False)
    embed.add_field(name="!security_help", value="Show this menu", inline=False)
    await ctx.send(embed=embed)

# ========== RUN ==========
bot.run(TOKEN)