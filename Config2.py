import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput
import asyncio
import sqlite3
import re
import os
import random
import aiohttp
import hashlib
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import threading

# ========== DISCORD BOT SETUP ==========
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 10000))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=["!", "/", "?"], intents=intents, help_command=None)

# ========== DATABASE ==========
conn = sqlite3.connect("configbot.db", check_same_thread=False)
c = conn.cursor()

# Core tables
c.execute('''CREATE TABLE IF NOT EXISTS autorole (guild_id INTEGER PRIMARY KEY, role_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS welcome (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, message TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS goodbye (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, message TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS warnings (user_id INTEGER, guild_id INTEGER, reason TEXT, mod_id INTEGER, timestamp TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS levels (user_id INTEGER, guild_id INTEGER, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0, PRIMARY KEY (user_id, guild_id))''')
c.execute('''CREATE TABLE IF NOT EXISTS messages (user_id INTEGER, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))''')
c.execute('''CREATE TABLE IF NOT EXISTS invites (user_id INTEGER PRIMARY KEY, code TEXT, uses INTEGER DEFAULT 0, fake INTEGER DEFAULT 0, bonus INTEGER DEFAULT 0, left INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS invite_uses (inviter_id INTEGER, joiner_id INTEGER, join_date TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS voice_activity (user_id INTEGER, date TEXT, minutes INTEGER, PRIMARY KEY (user_id, date))''')
c.execute('''CREATE TABLE IF NOT EXISTS tickets (channel_id INTEGER PRIMARY KEY, user_id INTEGER, guild_id INTEGER, status TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS ticket_config (guild_id INTEGER PRIMARY KEY, category_id INTEGER, support_role_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS giveaways (message_id INTEGER PRIMARY KEY, channel_id INTEGER, prize TEXT, end_time TIMESTAMP, winners INTEGER, hosted_by INTEGER, entries TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS reaction_roles (message_id INTEGER, emoji TEXT, role_id INTEGER, PRIMARY KEY (message_id, emoji))''')
c.execute('''CREATE TABLE IF NOT EXISTS reminders (user_id INTEGER, reminder TEXT, timestamp TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS afk (user_id INTEGER, guild_id INTEGER, reason TEXT, timestamp TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS security_config (guild_id INTEGER PRIMARY KEY, automod INTEGER DEFAULT 0, antinuke INTEGER DEFAULT 0, trap_channel INTEGER, log_channel INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS whitelist (user_id INTEGER, guild_id INTEGER, PRIMARY KEY (user_id, guild_id))''')
c.execute('''CREATE TABLE IF NOT EXISTS verification (guild_id INTEGER PRIMARY KEY, role_id INTEGER, channel_id INTEGER, log_channel_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS verify_codes (code TEXT PRIMARY KEY, user_id INTEGER, guild_id INTEGER, expires TIMESTAMP)''')
conn.commit()

# ========== BAD WORDS ==========
bad_words = [
    "fuck", "shit", "asshole", "bitch", "damn", "hell", "stupid", "idiot", "dumb", "retard",
    "cunt", "dick", "pussy", "cock", "whore", "slut", "bastard", "twat", "fag", "faggot",
    "nigger", "nigga", "chink", "spic", "kike", "gook", "wetback", "cracker", "honky",
    "f u c k", "f*ck", "s h i t", "sh*t", "b i t c h", "b*tch", "motherfucker", "rape", "kys"
]

# ========== STORAGE ==========
AUTOROLE_ID = None
WELCOME_CHANNEL_ID = None
LEAVE_CHANNEL_ID = None
automod_enabled = {}
antinuke_enabled = {}
trap_channel = {}
log_channel = {}
voice_start_times = {}
join_tracker = {}
message_counter = {}

# ========== HELPER FUNCTIONS ==========
def contains_bad_words(text):
    for word in bad_words:
        if word in text.lower():
            return True
    return False

async def add_warning(user_id, guild_id, reason, mod_id):
    c.execute("INSERT INTO warnings (user_id, guild_id, reason, mod_id, timestamp) VALUES (?, ?, ?, ?, ?)", (user_id, guild_id, reason, mod_id, datetime.now()))
    conn.commit()

async def log_action(guild_id, message):
    if log_channel.get(guild_id):
        channel = bot.get_channel(log_channel[guild_id])
        if channel:
            embed = discord.Embed(title="🛡️ Log", description=message, color=discord.Color.red(), timestamp=datetime.now())
            await channel.send(embed=embed)

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

# ========== REMINDERS TASK ==========
@tasks.loop(seconds=30)
async def check_reminders():
    now = datetime.now()
    c.execute("SELECT user_id, reminder FROM reminders WHERE timestamp <= ?", (now,))
    for uid, reminder in c.fetchall():
        user = bot.get_user(uid)
        if user:
            await user.send(f"⏰ Reminder: {reminder}")
    c.execute("DELETE FROM reminders WHERE timestamp <= ?", (now,))
    conn.commit()

# ========== ON_MESSAGE EVENT ==========
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # AFK check
    c.execute("SELECT user_id, reason FROM afk WHERE guild_id = ?", (message.guild.id,))
    for uid, reason in c.fetchall():
        if message.mentions and uid in [m.id for m in message.mentions]:
            await message.channel.send(f"⚠️ <@{uid}> is AFK: {reason}", delete_after=10)
            break
    c.execute("DELETE FROM afk WHERE user_id = ? AND guild_id = ?", (message.author.id, message.guild.id))
    
    # Message counting & leveling
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO messages (user_id, date, count) VALUES (?, ?, 1) ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1", (message.author.id, today))
    
    c.execute("SELECT xp, level FROM levels WHERE user_id = ? AND guild_id = ?", (message.author.id, message.guild.id))
    result = c.fetchone()
    if result:
        xp, level = result
        xp += random.randint(10, 20)
        new_level = xp // 100
        if new_level > level:
            await message.channel.send(f"🎉 {message.author.mention} leveled up to **Level {new_level}**!")
            c.execute("UPDATE levels SET xp = ?, level = ? WHERE user_id = ? AND guild_id = ?", (xp, new_level, message.author.id, message.guild.id))
        else:
            c.execute("UPDATE levels SET xp = ? WHERE user_id = ? AND guild_id = ?", (xp, message.author.id, message.guild.id))
    else:
        c.execute("INSERT INTO levels (user_id, guild_id, xp, level) VALUES (?, ?, ?, ?)", (message.author.id, message.guild.id, 10, 0))
    conn.commit()
    
    # Auto-mod
    guild_id = message.guild.id
    if automod_enabled.get(guild_id, 0) == 1:
        await check_spam(message)
        if contains_bad_words(message.content):
            await message.delete()
            await message.channel.send(f"{message.author.mention} No bad words!", delete_after=3)
    
    # Trap channel
    if trap_channel.get(guild_id) == message.channel.id:
        await message.author.ban(reason="Typed in trap channel")
        await log_action(guild_id, f"🔨 BANNED {message.author.mention} (trap channel)")
        return
    
    await bot.process_commands(message)

# ========== VOICE STATE ==========
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        voice_start_times[member.id] = datetime.now()
    elif before.channel is not None and after.channel is None:
        if member.id in voice_start_times:
            start = voice_start_times.pop(member.id)
            minutes = int((datetime.now() - start).total_seconds() / 60)
            if minutes > 0:
                today = datetime.now().strftime("%Y-%m-%d")
                c.execute("INSERT INTO voice_activity (user_id, date, minutes) VALUES (?, ?, ?) ON CONFLICT(user_id, date) DO UPDATE SET minutes = minutes + ?", (member.id, today, minutes, minutes))
                conn.commit()

# ========== MEMBER JOIN/LEAVE ==========
@bot.event
async def on_member_join(member):
    if AUTOROLE_ID:
        role = member.guild.get_role(AUTOROLE_ID)
        if role:
            await member.add_roles(role)
    if WELCOME_CHANNEL_ID:
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if channel:
            await channel.send(f"✨ Welcome {member.mention} to {member.guild.name}!")
    
    guild_id = member.guild.id
    if guild_id not in join_tracker:
        join_tracker[guild_id] = []
    join_tracker[guild_id].append(datetime.now())
    join_tracker[guild_id] = [t for t in join_tracker[guild_id] if (datetime.now() - t).seconds < 30]
    if len(join_tracker[guild_id]) > 5 and antinuke_enabled.get(guild_id, 0) == 1:
        await member.guild.edit(verification_level=discord.VerificationLevel.high)
        await log_action(guild_id, "⚠️ RAID DETECTED! Server verification increased")

@bot.event
async def on_member_remove(member):
    if LEAVE_CHANNEL_ID:
        channel = member.guild.get_channel(LEAVE_CHANNEL_ID)
        if channel:
            await channel.send(f"👋 {member.name} left the server.")

# ========== REACTION ROLES ==========
@bot.event
async def on_raw_reaction_add(payload):
    if payload.member.bot:
        return
    c.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", (payload.message_id, str(payload.emoji)))
    result = c.fetchone()
    if result:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(result[0])
        if role:
            await payload.member.add_roles(role)

# ========== ON_READY ==========
@bot.event
async def on_ready():
    print(f"✅ ConfigBot is online in {len(bot.guilds)} servers!")
    await bot.change_presence(activity=discord.Game(name="!help | 200+ commands"))
    
    # Load settings
    c.execute("SELECT guild_id, automod, antinuke, trap_channel, log_channel FROM security_config")
    for row in c.fetchall():
        gid, auto, anti, trap, logc = row
        automod_enabled[gid] = auto
        antinuke_enabled[gid] = anti
        trap_channel[gid] = trap
        log_channel[gid] = logc
    
    # Start reminders loop
    check_reminders.start()

# ========== UTILITY COMMANDS ==========
@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.command()
async def test(ctx):
    await ctx.send("✅ ConfigBot is working!")

@bot.command()
async def hello(ctx):
    await ctx.send(f"👋 Hello {ctx.author.mention}!")

@bot.command()
async def info(ctx):
    embed = discord.Embed(title="⚙️ ConfigBot", description="All-in-one Discord bot", color=discord.Color.blue())
    embed.add_field(name="Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="Commands", value="200+", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member.name}'s Avatar", color=discord.Color.blue())
    embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=guild.name, color=discord.Color.green())
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=member.name, color=discord.Color.blue())
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%b %d, %Y"), inline=True)
    embed.add_field(name="Joined Discord", value=member.created_at.strftime("%b %d, %Y"), inline=True)
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def poll(ctx, question, *options):
    if len(options) < 2:
        await ctx.send("❌ Need at least 2 options!")
        return
    if len(options) > 10:
        await ctx.send("❌ Max 10 options!")
        return
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    description = "\n".join([f"{emojis[i]} {opt}" for i, opt in enumerate(options)])
    embed = discord.Embed(title=f"📊 {question}", description=description, color=discord.Color.blue())
    msg = await ctx.send(embed=embed)
    for i in range(len(options)):
        await msg.add_reaction(emojis[i])

@bot.command()
async def choose(ctx, *choices):
    if len(choices) < 2:
        await ctx.send("❌ Give at least 2 options!")
        return
    await ctx.send(f"🤔 I choose: **{random.choice(choices)}**")

@bot.command()
async def roll(ctx, dice: str = "1d6"):
    try:
        count, sides = map(int, dice.split('d'))
        if count > 100:
            await ctx.send("❌ Too many dice")
            return
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        await ctx.send(f"🎲 Rolling {dice}: **{total}** | ({', '.join(map(str, rolls))})")
    except:
        await ctx.send("❌ Use format: 2d20")

@bot.command()
async def flip(ctx):
    await ctx.send(f"🪙 **{random.choice(['Heads', 'Tails'])}**")

@bot.command()
async def invite(ctx):
    await ctx.send("📨 [Invite ConfigBot](https://discord.com/api/oauth2/authorize?client_id=1502478610814992404&permissions=8&scope=bot%20applications.commands)")

@bot.command()
async def uptime(ctx):
    delta = datetime.now() - bot.start_time if hasattr(bot, 'start_time') else timedelta(seconds=0)
    await ctx.send(f"⏰ Uptime: {delta.seconds // 3600}h {(delta.seconds % 3600) // 60}m {delta.seconds % 60}s")

@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    c.execute("SELECT xp, level FROM levels WHERE user_id = ? AND guild_id = ?", (member.id, ctx.guild.id))
    result = c.fetchone()
    if result:
        xp, level = result
        needed = 100 - (xp % 100)
        embed = discord.Embed(title=f"📊 {member.name}'s Rank", color=discord.Color.blue())
        embed.add_field(name="Level", value=level, inline=True)
        embed.add_field(name="XP", value=f"{xp % 100}/100", inline=True)
        embed.add_field(name="Next Level", value=f"{needed} XP needed", inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send("No XP data yet. Start chatting!")

@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT user_id, level, xp FROM levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10", (ctx.guild.id,))
    top = c.fetchall()
    if not top:
        await ctx.send("No data yet!")
        return
    embed = discord.Embed(title="🏆 Level Leaderboard", color=discord.Color.gold())
    for i, (uid, lvl, xp) in enumerate(top, 1):
        user = bot.get_user(uid)
        name = user.name if user else f"User {uid}"
        embed.add_field(name=f"{i}. {name}", value=f"Level {lvl} ({xp} XP)", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def stats(ctx):
    guild = ctx.guild
    humans = sum(1 for m in guild.members if not m.bot)
    bots = guild.member_count - humans
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT SUM(count) FROM messages WHERE date = ?", (today,))
    msgs_today = c.fetchone()[0] or 0
    embed = discord.Embed(title="📊 Server Stats", color=discord.Color.blue())
    embed.add_field(name="Members", value=f"Total: {guild.member_count}\nHumans: {humans}\nBots: {bots}", inline=True)
    embed.add_field(name="Messages Today", value=msgs_today, inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def invites(ctx, member: discord.Member = None):
    member = member or ctx.author
    c.execute("SELECT uses, bonus, left FROM invites WHERE user_id = ?", (member.id,))
    result = c.fetchone()
    if result:
        uses, bonus, left = result
        total = uses + bonus
        embed = discord.Embed(title=f"📨 {member.name}'s Invites", color=discord.Color.green())
        embed.add_field(name="Total", value=total, inline=True)
        embed.add_field(name="Real", value=uses, inline=True)
        embed.add_field(name="Left", value=left, inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"{member.mention} has no invites.")

@bot.command()
async def inv_leaderboard(ctx):
    c.execute("SELECT user_id, uses + bonus as total FROM invites ORDER BY total DESC LIMIT 10")
    top = c.fetchall()
    if not top:
        await ctx.send("No data yet.")
        return
    embed = discord.Embed(title="🏆 Invite Leaderboard", color=discord.Color.gold())
    for i, (uid, total) in enumerate(top, 1):
        user = bot.get_user(uid)
        name = user.name if user else f"User {uid}"
        embed.add_field(name=f"{i}. {name}", value=f"{total} invites", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def msg_leaderboard(ctx, days: int = 7):
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    c.execute("SELECT user_id, SUM(count) as total FROM messages WHERE date >= ? GROUP BY user_id ORDER BY total DESC LIMIT 10", (start,))
    top = c.fetchall()
    if not top:
        await ctx.send("No data yet.")
        return
    embed = discord.Embed(title=f"💬 Message Leaderboard (Last {days} days)", color=discord.Color.blue())
    for i, (uid, total) in enumerate(top, 1):
        user = bot.get_user(uid)
        name = user.name if user else f"User {uid}"
        embed.add_field(name=f"{i}. {name}", value=f"{total} messages", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def voice_leaderboard(ctx, days: int = 7):
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    c.execute("SELECT user_id, SUM(minutes) as total FROM voice_activity WHERE date >= ? GROUP BY user_id ORDER BY total DESC LIMIT 10", (start,))
    top = c.fetchall()
    if not top:
        await ctx.send("No data yet.")
        return
    embed = discord.Embed(title=f"🎙️ Voice Leaderboard (Last {days} days)", color=discord.Color.purple())
    for i, (uid, minutes) in enumerate(top, 1):
        user = bot.get_user(uid)
        name = user.name if user else f"User {uid}"
        hours = minutes // 60
        mins = minutes % 60
        embed.add_field(name=f"{i}. {name}", value=f"{hours}h {mins}m", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def scan(ctx, member: discord.Member):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Admin only.")
        return
    c.execute("SELECT DISTINCT joiner_id FROM invite_uses WHERE inviter_id IN (SELECT inviter_id FROM invite_uses WHERE joiner_id = ?) AND joiner_id != ?", (member.id, member.id))
    alts = c.fetchall()
    if alts:
        await ctx.send(f"⚠️ Possible alts for {member.mention}: {', '.join([f'<@{a[0]}>' for a in alts[:5]])}")
    else:
        await ctx.send(f"✅ No alts found for {member.mention}")

@bot.command()
async def alt_scan(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Admin only.")
        return
    await ctx.send("🔍 Scanning for alt accounts...")
    c.execute("SELECT inviter_id, COUNT(DISTINCT joiner_id) as alts FROM invite_uses GROUP BY inviter_id HAVING alts > 1 ORDER BY alts DESC LIMIT 10")
    results = c.fetchall()
    if results:
        embed = discord.Embed(title="🔍 Alt Account Detections", color=discord.Color.orange())
        for inviter, alts in results:
            embed.add_field(name=f"<@{inviter}>", value=f"{alts} possible alts", inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("✅ No alt accounts detected.")

# ========== MODERATION COMMANDS ==========
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 Kicked {member.mention} | {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 Banned {member.mention} | {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, member):
    banned = [entry async for entry in ctx.guild.bans()]
    name = member.split('#')[0]
    for entry in banned:
        if entry.user.name == name:
            await ctx.guild.unban(entry.user)
            await ctx.send(f"✅ Unbanned {entry.user.mention}")
            return
    await ctx.send("❌ User not found")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    if amount > 100:
        await ctx.send("❌ Max 100")
        return
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"✅ Cleared {amount} messages", delete_after=2)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"🔒 Locked {channel.mention}")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=None)
    await ctx.send(f"🔓 Unlocked {channel.mention}")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason="No reason"):
    await member.timeout(timedelta(minutes=minutes), reason=reason)
    await ctx.send(f"⏰ Timed out {member.mention} for {minutes} minutes")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    await add_warning(member.id, ctx.guild.id, reason, ctx.author.id)
    await ctx.send(f"⚠️ Warned {member.mention} | {reason}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warnings(ctx, member: discord.Member):
    c.execute("SELECT reason, mod_id, timestamp FROM warnings WHERE user_id = ? AND guild_id = ?", (member.id, ctx.guild.id))
    warns = c.fetchall()
    if not warns:
        await ctx.send(f"{member.mention} has no warnings.")
        return
    embed = discord.Embed(title=f"⚠️ Warnings for {member.name}", color=discord.Color.orange())
    for i, (reason, mod_id, ts) in enumerate(warns[:10], 1):
        embed.add_field(name=f"#{i}", value=f"Reason: {reason}\nMod: <@{mod_id}>\nTime: {str(ts)[:19]}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def slowmode(ctx, seconds: int):
    if seconds > 21600:
        await ctx.send("❌ Max 6 hours")
        return
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"⏱️ Slowmode: {seconds}s")

# ========== SETUP COMMANDS ==========
@bot.command()
@commands.has_permissions(administrator=True)
async def setwelcome(ctx, channel: discord.TextChannel):
    global WELCOME_CHANNEL_ID
    WELCOME_CHANNEL_ID = channel.id
    c.execute("INSERT OR REPLACE INTO welcome (guild_id, channel_id, message) VALUES (?, ?, ?)", (ctx.guild.id, channel.id, "Welcome {user} to {server}!"))
    conn.commit()
    await ctx.send(f"✅ Welcome channel: {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setleave(ctx, channel: discord.TextChannel):
    global LEAVE_CHANNEL_ID
    LEAVE_CHANNEL_ID = channel.id
    c.execute("INSERT OR REPLACE INTO goodbye (guild_id, channel_id, message) VALUES (?, ?, ?)", (ctx.guild.id, channel.id, "Goodbye {user}!"))
    conn.commit()
    await ctx.send(f"✅ Leave channel: {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setautorole(ctx, role: discord.Role):
    global AUTOROLE_ID
    AUTOROLE_ID = role.id
    c.execute("INSERT OR REPLACE INTO autorole (guild_id, role_id) VALUES (?, ?)", (ctx.guild.id, role.id))
    conn.commit()
    await ctx.send(f"✅ Auto-role: {role.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setlog(ctx, channel: discord.TextChannel):
    c.execute("INSERT OR REPLACE INTO security_config (guild_id, log_channel) VALUES (?, ?)", (ctx.guild.id, channel.id))
    conn.commit()
    log_channel[ctx.guild.id] = channel.id
    await ctx.send(f"✅ Log channel: {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def settrap(ctx, channel: discord.TextChannel):
    c.execute("INSERT OR REPLACE INTO security_config (guild_id, trap_channel) VALUES (?, ?)", (ctx.guild.id, channel.id))
    conn.commit()
    trap_channel[ctx.guild.id] = channel.id
    await ctx.send(f"✅ Trap channel: {channel.mention} (typing = instant ban)")

# ========== SECURITY PANEL ==========
class SecurityPanel(View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    
    @discord.ui.button(label="🛡️ Auto-Mod", style=discord.ButtonStyle.primary, row=0)
    async def automod_btn(self, interaction: discord.Interaction, button: Button):
        current = automod_enabled.get(self.guild_id, 0)
        new = 1 if current == 0 else 0
        automod_enabled[self.guild_id] = new
        c.execute("INSERT OR REPLACE INTO security_config (guild_id, automod) VALUES (?, ?)", (self.guild_id, new))
        conn.commit()
        await interaction.response.send_message(f"✅ Auto-Mod {'ENABLED' if new else 'DISABLED'}", ephemeral=True)
        await log_action(self.guild_id, f"Auto-Mod {'ON' if new else 'OFF'} by {interaction.user.mention}")
    
    @discord.ui.button(label="🚨 Anti-Nuke", style=discord.ButtonStyle.danger, row=0)
    async def antinuke_btn(self, interaction: discord.Interaction, button: Button):
        current = antinuke_enabled.get(self.guild_id, 0)
        new = 1 if current == 0 else 0
        antinuke_enabled[self.guild_id] = new
        c.execute("INSERT OR REPLACE INTO security_config (guild_id, antinuke) VALUES (?, ?)", (self.guild_id, new))
        conn.commit()
        await interaction.response.send_message(f"✅ Anti-Nuke {'ENABLED' if new else 'DISABLED'}", ephemeral=True)
        await log_action(self.guild_id, f"Anti-Nuke {'ON' if new else 'OFF'} by {interaction.user.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def security_panel(ctx):
    embed = discord.Embed(title="🛡️ Security Panel", color=discord.Color.blue())
    embed.add_field(name="Auto-Mod", value="Spam + bad word filter", inline=False)
    embed.add_field(name="Anti-Nuke", value="Raid detection", inline=False)
    view = SecurityPanel(ctx.guild.id)
    await ctx.send(embed=embed, view=view)

@bot.command()
@commands.has_permissions(administrator=True)
async def security_status(ctx):
    auto = automod_enabled.get(ctx.guild.id, 0)
    anti = antinuke_enabled.get(ctx.guild.id, 0)
    trap = trap_channel.get(ctx.guild.id, "Not set")
    embed = discord.Embed(title="🛡️ Security Status", color=discord.Color.blue())
    embed.add_field(name="Auto-Mod", value="✅ ON" if auto else "❌ OFF", inline=True)
    embed.add_field(name="Anti-Nuke", value="✅ ON" if anti else "❌ OFF", inline=True)
    embed.add_field(name="Trap Channel", value=f"<#{trap}>" if trap != "Not set" else "❌ Not set", inline=True)
    await ctx.send(embed=embed)

# ========== TICKET SYSTEM ==========
class TicketModal(Modal):
    def __init__(self):
        super().__init__(title="Create Ticket")
        self.reason = TextInput(label="Reason", placeholder="Why do you need support?", required=True)
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        c.execute("SELECT category_id, support_role_id FROM ticket_config WHERE guild_id = ?", (interaction.guild.id,))
        config = c.fetchone()
        if not config:
            await interaction.response.send_message("❌ Ticket system not set up.", ephemeral=True)
            return
        category = interaction.guild.get_channel(config[0])
        if not category:
            await interaction.response.send_message("❌ Category not found.", ephemeral=True)
            return
        ticket_num = len([c for c in category.channels if c.name.startswith("ticket-")]) + 1
        channel = await interaction.guild.create_text_channel(f"ticket-{ticket_num:04d}", category=category)
        await channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        if config[1]:
            support_role = interaction.guild.get_role(config[1])
            if support_role:
                await channel.set_permissions(support_role, view_channel=True, send_messages=True)
        await channel.send(f"🎫 Ticket #{ticket_num:04d} opened by {interaction.user.mention}\nReason: {self.reason.value}\nType `!close` to close.")
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

class TicketButton(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, emoji="🎫")
    async def ticket_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(TicketModal())

@bot.command()
@commands.has_permissions(administrator=True)
async def ticketpanel(ctx, category: discord.CategoryChannel, role: discord.Role = None):
    c.execute("INSERT OR REPLACE INTO ticket_config (guild_id, category_id, support_role_id) VALUES (?, ?, ?)", (ctx.guild.id, category.id, role.id if role else None))
    conn.commit()
    embed = discord.Embed(title="🎫 Support Tickets", description="Click below to create a ticket", color=discord.Color.blue())
    view = TicketButton()
    await ctx.send(embed=embed, view=view)

@bot.command()
async def close(ctx):
    if not ctx.channel.name.startswith("ticket-"):
        await ctx.send("❌ Not a ticket channel.")
        return
    await ctx.send("🔒 Closing in 5 seconds...")
    await asyncio.sleep(5)
    await ctx.channel.delete()

# ========== VERIFICATION PANEL ==========
class VerifyButton(View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    
    @discord.ui.button(label="Verify", style=discord.ButtonStyle.success, emoji="✅")
    async def verify_btn(self, interaction: discord.Interaction, button: Button):
        c.execute("SELECT role_id, channel_id, log_channel_id FROM verification WHERE guild_id = ?", (self.guild_id,))
        result = c.fetchone()
        if not result:
            await interaction.response.send_message("❌ Verification not set up.", ephemeral=True)
            return
        
        role_id, channel_id, log_channel_id = result
        role = interaction.guild.get_role(role_id)
        
        # Generate unique code
        code = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(minutes=10)
        c.execute("INSERT INTO verify_codes (code, user_id, guild_id, expires) VALUES (?, ?, ?, ?)", (code, interaction.user.id, self.guild_id, expires))
        conn.commit()
        
        # Create verification link
        base_url = os.getenv("BASE_URL", "https://your-bot.onrender.com")
        verify_url = f"{base_url}/verify/{code}"
        
        embed = discord.Embed(
            title="✅ Verification Required",
            description=f"Click the link below to verify yourself:\n{verify_url}\n\nThis link expires in 10 minutes.",
            color=discord.Color.blue()
        )
        await interaction.user.send(embed=embed)
        await interaction.response.send_message("✅ I've sent you a verification link in DMs!", ephemeral=True)

@bot.command()
@commands.has_permissions(administrator=True)
async def verifypanel(ctx, role: discord.Role, channel: discord.TextChannel, log_channel: discord.TextChannel):
    """!verifypanel @role #verify-channel #log-channel - Set up verification system"""
    c.execute("INSERT OR REPLACE INTO verification (guild_id, role_id, channel_id, log_channel_id) VALUES (?, ?, ?, ?)", (ctx.guild.id, role.id, channel.id, log_channel.id))
    conn.commit()
    
    # Set channel permissions
    await channel.set_permissions(ctx.guild.default_role, view_channel=True, send_messages=False)
    await channel.set_permissions(role, view_channel=True, send_messages=True)
    
    embed = discord.Embed(
        title="✅ Verification Required",
        description="Click the **Verify** button below to verify yourself. You will receive a private link in DMs.\n\nAfter verification, you will gain access to the server.",
        color=discord.Color.green()
    )
    view = VerifyButton(ctx.guild.id)
    await channel.send(embed=embed, view=view)
    
    await ctx.send(f"✅ Verification system set up!\nRole: {role.mention}\nChannel: {channel.mention}\nLogs: {log_channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def unverify(ctx, member: discord.Member):
    """!unverify @user - Remove verified role from user"""
    c.execute("SELECT role_id FROM verification WHERE guild_id = ?", (ctx.guild.id,))
    result = c.fetchone()
    if result:
        role = ctx.guild.get_role(result[0])
        if role and role in member.roles:
            await member.remove_roles(role)
            await ctx.send(f"✅ Removed verified role from {member.mention}")
        else:
            await ctx.send(f"{member.mention} does not have the verified role.")
    else:
        await ctx.send("❌ Verification system not set up.")

# ========== GIVEAWAY ==========
@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway(ctx, winners: int, duration: str, *, prize):
    time_map = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    unit = duration[-1]
    try:
        seconds = int(duration[:-1]) * time_map[unit]
    except:
        await ctx.send("❌ Use 30s, 5m, 2h, 1d")
        return
    end = datetime.now() + timedelta(seconds=seconds)
    embed = discord.Embed(title="🎉 GIVEAWAY!", description=f"Prize: {prize}\nWinners: {winners}\nEnds: {discord.utils.format_dt(end, 'R')}", color=discord.Color.gold())
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")
    
    await asyncio.sleep(seconds)
    new_msg = await ctx.channel.fetch_message(msg.id)
    users = []
    for reaction in new_msg.reactions:
        if str(reaction.emoji) == "🎉":
            async for user in reaction.users():
                if not user.bot:
                    users.append(user)
    if len(users) == 0:
        await ctx.send("No participants.")
        return
    winners_list = random.sample(users, min(winners, len(users)))
    await ctx.send(f"🎉 Winners: {', '.join([w.mention for w in winners_list])}")

# ========== REACTION ROLES COMMAND ==========
@bot.command()
@commands.has_permissions(administrator=True)
async def addreactrole(ctx, message_id: int, emoji, role: discord.Role):
    try:
        msg = await ctx.channel.fetch_message(message_id)
        await msg.add_reaction(emoji)
        c.execute("INSERT INTO reaction_roles (message_id, emoji, role_id) VALUES (?, ?, ?)", (message_id, str(emoji), role.id))
        conn.commit()
        await ctx.send(f"✅ Added {emoji} → {role.mention}")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

# ========== REMINDER ==========
@bot.command()
async def remindme(ctx, duration: str, *, reminder):
    time_map = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    unit = duration[-1]
    try:
        seconds = int(duration[:-1]) * time_map[unit]
    except:
        await ctx.send("❌ Use 30s, 5m, 2h, 1d")
        return
    remind_time = datetime.now() + timedelta(seconds=seconds)
    c.execute("INSERT INTO reminders (user_id, reminder, timestamp) VALUES (?, ?, ?)", (ctx.author.id, reminder, remind_time))
    conn.commit()
    await ctx.send(f"✅ I'll remind you in {duration}!")

# ========== AFK ==========
@bot.command()
async def afk(ctx, *, reason="AFK"):
    c.execute("INSERT OR REPLACE INTO afk (user_id, guild_id, reason, timestamp) VALUES (?, ?, ?, ?)", (ctx.author.id, ctx.guild.id, reason, datetime.now()))
    conn.commit()
    await ctx.send(f"✅ {ctx.author.mention} is now AFK: {reason}")

# ========== FUN COMMANDS ==========
@bot.command()
async def meme(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://meme-api.com/gimme") as resp:
            data = await resp.json()
            embed = discord.Embed(title=data["title"], color=discord.Color.blue())
            embed.set_image(url=data["url"])
            await ctx.send(embed=embed)

@bot.command()
async def dm(ctx, member: discord.Member, *, message):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Admin only")
        return
    await member.send(f"📨 From {ctx.author.name}: {message}")
    await ctx.send(f"✅ Sent DM to {member.name}")

# ========== HELP COMMAND ==========
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="⚙️ ConfigBot - 200+ Commands", color=discord.Color.green())
    embed.add_field(name="📌 Utility", value="`ping`, `test`, `hello`, `info`, `avatar`, `serverinfo`, `userinfo`, `poll`, `choose`, `roll`, `flip`, `invite`, `uptime`", inline=False)
    embed.add_field(name="📊 Leveling & Stats", value="`rank`, `leaderboard`, `stats`, `invites`, `inv_leaderboard`, `msg_leaderboard`, `voice_leaderboard`, `scan`, `alt_scan`", inline=False)
    embed.add_field(name="🛡️ Moderation", value="`kick`, `ban`, `unban`, `clear`, `lock`, `unlock`, `timeout`, `warn`, `warnings`, `slowmode`", inline=False)
    embed.add_field(name="🔧 Setup", value="`setwelcome`, `setleave`, `setautorole`, `setlog`, `settrap`, `security_panel`, `security_status`", inline=False)
    embed.add_field(name="🎫 Tickets", value="`ticketpanel`, `close`", inline=False)
    embed.add_field(name="✅ Verification", value="`verifypanel`", inline=False)
    embed.add_field(name="🎁 Giveaways", value="`giveaway`", inline=False)
    embed.add_field(name="🔔 Other", value="`addreactrole`, `remindme`, `afk`, `meme`, `dm`", inline=False)
    embed.set_footer(text="Made for Configuration2")
    await ctx.send(embed=embed)

# ========== ERROR HANDLING ==========
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission.", delete_after=3)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing argument. Type `!help`", delete_after=3)
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ Error: {error}", delete_after=5)

# ========== FLASK WEB SERVER (For Render & Verification) ==========
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "✅ ConfigBot is alive! Verification system ready."

@flask_app.route('/verify/<code>')
def verify(code):
    c.execute("SELECT user_id, guild_id, expires FROM verify_codes WHERE code = ?", (code,))
    result = c.fetchone()
    
    if not result:
        return "<h1>❌ Invalid or expired verification link.</h1><p>Please request a new link.</p>"
    
    user_id, guild_id, expires = result
    expires_time = datetime.fromisoformat(expires) if isinstance(expires, str) else expires
    
    if datetime.now() > expires_time:
        c.execute("DELETE FROM verify_codes WHERE code = ?", (code,))
        conn.commit()
        return "<h1>❌ Verification link expired.</h1><p>Please click the verify button again for a new link.</p>"
    
    # Get guild and user
    guild = bot.get_guild(guild_id)
    if guild:
        member = guild.get_member(user_id)
        if member:
            c.execute("SELECT role_id FROM verification WHERE guild_id = ?", (guild_id,))
            role_result = c.fetchone()
            if role_result:
                role = guild.get_role(role_result[0])
                if role:
                    member.add_roles(role)
                    
                    # Log verification
                    c.execute("SELECT log_channel_id FROM verification WHERE guild_id = ?", (guild_id,))
                    log_result = c.fetchone()
                    if log_result and log_result[0]:
                        log_channel = guild.get_channel(log_result[0])
                        if log_channel:
                            log_embed = discord.Embed(
                                title="✅ User Verified",
                                description=f"{member.mention} has successfully verified.",
                                color=discord.Color.green(),
                                timestamp=datetime.now()
                            )
                            asyncio.create_task(log_channel.send(embed=log_embed))
    
    # Delete used code
    c.execute("DELETE FROM verify_codes WHERE code = ?", (code,))
    conn.commit()
    
    return """
    <html>
    <head>
        <title>Verification Successful</title>
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; background: #1e1e2f; color: white; }
            .container { background: #2c2f3a; padding: 40px; border-radius: 10px; max-width: 500px; margin: auto; }
            h1 { color: #57f287; }
            p { color: #ccc; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✅ Verification Successful!</h1>
            <p>You have been verified. You can now close this page and return to Discord.</p>
        </div>
    </body>
    </html>
    """

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT)

# ========== RUN ==========
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print(f"🌐 Web server started on port {PORT}")
    bot.start_time = datetime.now()
    bot.run(TOKEN)