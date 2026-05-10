import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio
import sqlite3
from collections import defaultdict
import re

TOKEN = "TOKEN"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== DATABASE SETUP ==========
conn = sqlite3.connect("server_stats.db")
c = conn.cursor()

# Messages table
c.execute('''CREATE TABLE IF NOT EXISTS messages (
    user_id INTEGER,
    date TEXT,
    count INTEGER,
    PRIMARY KEY (user_id, date)
)''')

# Invites table
c.execute('''CREATE TABLE IF NOT EXISTS invites (
    user_id INTEGER PRIMARY KEY,
    code TEXT,
    uses INTEGER DEFAULT 0,
    fake INTEGER DEFAULT 0,
    bonus INTEGER DEFAULT 0,
    left INTEGER DEFAULT 0
)''')

# Invite uses table
c.execute('''CREATE TABLE IF NOT EXISTS invite_uses (
    inviter_id INTEGER,
    joiner_id INTEGER,
    join_date TEXT
)''')

# Voice activity table
c.execute('''CREATE TABLE IF NOT EXISTS voice_activity (
    user_id INTEGER,
    date TEXT,
    minutes INTEGER,
    PRIMARY KEY (user_id, date)
)''')

conn.commit()

# ========== CONFIGURATION ==========
STATS_CHANNEL_ID = 123456789012345678  # Channel where stats are posted
LOG_CHANNEL_ID = 123456789012345678   # Channel for logs
STAFF_ROLE_ID = 123456789012345678    # Staff role ID
VERIFIED_ROLE_ID = 123456789012345678 # Verified role ID

stats_message_id = None
voice_start_times = {}

# ========== MESSAGE COUNTER ==========
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Count messages
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO messages (user_id, date, count) VALUES (?, ?, 1) ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1",
              (message.author.id, today))
    conn.commit()
    
    await bot.process_commands(message)

# ========== VOICE ACTIVITY TRACKER ==========
@bot.event
async def on_voice_state_update(member, before, after):
    # User joined voice channel
    if before.channel is None and after.channel is not None:
        voice_start_times[member.id] = datetime.now()
    
    # User left voice channel
    elif before.channel is not None and after.channel is None:
        if member.id in voice_start_times:
            start = voice_start_times.pop(member.id)
            minutes = int((datetime.now() - start).total_seconds() / 60)
            if minutes > 0:
                today = datetime.now().strftime("%Y-%m-%d")
                c.execute("INSERT INTO voice_activity (user_id, date, minutes) VALUES (?, ?, ?) ON CONFLICT(user_id, date) DO UPDATE SET minutes = minutes + ?",
                          (member.id, today, minutes, minutes))
                conn.commit()

# ========== INVITE TRACKER ==========
@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online!")
    update_stats.start()
    
    # Cache all invites on startup
    for guild in bot.guilds:
        await guild.invites()

@bot.event
async def on_invite_create(invite):
    c.execute("INSERT OR REPLACE INTO invites (user_id, code, uses, fake, bonus, left) VALUES (?, ?, 0, 0, 0, 0)",
              (invite.inviter.id, invite.code))
    conn.commit()

@bot.event
async def on_member_join(member):
    # Find which invite was used
    invites_before = {invite.code: invite.uses for invite in await member.guild.invites()}
    await asyncio.sleep(2)
    invites_after = {invite.code: invite.uses for invite in await member.guild.invites()}
    
    for code, uses_after in invites_after.items():
        uses_before = invites_before.get(code, 0)
        if uses_after > uses_before:
            c.execute("SELECT user_id FROM invites WHERE code = ?", (code,))
            result = c.fetchone()
            if result:
                inviter_id = result[0]
                c.execute("INSERT INTO invite_uses (inviter_id, joiner_id, join_date) VALUES (?, ?, ?)",
                          (inviter_id, member.id, datetime.now()))
                c.execute("UPDATE invites SET uses = uses + 1 WHERE code = ?", (code,))
                conn.commit()
                
                # Log to staff channel
                log_channel = bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(f"📥 {member.mention} joined using invite from <@{inviter_id}>")
            break

@bot.event
async def on_member_remove(member):
    c.execute("SELECT inviter_id FROM invite_uses WHERE joiner_id = ?", (member.id,))
    result = c.fetchone()
    if result:
        c.execute("UPDATE invites SET left = left + 1 WHERE user_id = ?", (result[0],))
        conn.commit()

# ========== DAILY STATS UPDATE ==========
@tasks.loop(hours=1)
async def update_stats():
    await post_server_stats()

async def post_server_stats():
    global stats_message_id
    channel = bot.get_channel(STATS_CHANNEL_ID)
    if not channel:
        return
    
    guild = channel.guild
    
    # Member counts
    total_members = guild.member_count
    humans = sum(1 for m in guild.members if not m.bot)
    bots = total_members - humans
    verified = sum(1 for m in guild.members if VERIFIED_ROLE_ID in [r.id for r in m.roles])
    online = sum(1 for m in guild.members if m.status != discord.Status.offline)
    
    # Channel counts
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    forum_channels = len(guild.forums)
    categories = len(guild.categories)
    
    # Messages today
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT SUM(count) FROM messages WHERE date = ?", (today,))
    messages_today = c.fetchone()[0] or 0
    
    # Messages this week
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    c.execute("SELECT SUM(count) FROM messages WHERE date >= ?", (week_ago,))
    messages_week = c.fetchone()[0] or 0
    
    # Messages all time
    c.execute("SELECT SUM(count) FROM messages")
    messages_total = c.fetchone()[0] or 0
    
    # Voice activity today
    c.execute("SELECT SUM(minutes) FROM voice_activity WHERE date = ?", (today,))
    voice_today = c.fetchone()[0] or 0
    
    # Top chatters today
    c.execute("SELECT user_id, count FROM messages WHERE date = ? ORDER BY count DESC LIMIT 5", (today,))
    top_chatters = c.fetchall()
    
    # Top inviters
    c.execute("SELECT user_id, uses + bonus FROM invites ORDER BY uses + bonus DESC LIMIT 5")
    top_inviters = c.fetchall()
    
    # Create embed
    embed = discord.Embed(
        title="📊 Server Statistics",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="👥 Members", 
                    value=f"Total: **{total_members}**\nHumans: {humans}\nBots: {bots}\nVerified: {verified}\nOnline: {online}", 
                    inline=True)
    
    embed.add_field(name="💬 Channels", 
                    value=f"Text: {text_channels}\nVoice: {voice_channels}\nForum: {forum_channels}\nCategories: {categories}", 
                    inline=True)
    
    embed.add_field(name="✉️ Messages", 
                    value=f"Today: **{messages_today}**\nThis Week: {messages_week}\nTotal: {messages_total}", 
                    inline=True)
    
    embed.add_field(name="🎙️ Voice Activity", 
                    value=f"Today: {voice_today} minutes", 
                    inline=True)
    
    if top_chatters:
        chatter_text = "\n".join([f"<@{uid}>: {count}" for uid, count in top_chatters])
        embed.add_field(name="🏆 Top Chatters Today", value=chatter_text, inline=False)
    
    if top_inviters:
        inviter_text = "\n".join([f"<@{uid}>: {total}" for uid, total in top_inviters])
        embed.add_field(name="📨 Top Inviters", value=inviter_text, inline=False)
    
    embed.set_footer(text=f"{guild.name} • Updates every hour")
    
    # Update or send new message
    global stats_message_id
    if stats_message_id:
        try:
            msg = await channel.fetch_message(stats_message_id)
            await msg.edit(embed=embed)
        except:
            msg = await channel.send(embed=embed)
            stats_message_id = msg.id
    else:
        msg = await channel.send(embed=embed)
        stats_message_id = msg.id

# ========== COMMANDS ==========

@bot.command()
async def stats(ctx):
    """!stats - Show current server stats"""
    await post_server_stats()
    await ctx.send("✅ Stats updated!", delete_after=3)

@bot.command()
async def invites(ctx, member: discord.Member = None):
    """!invites @user - Check how many invites a user has"""
    member = member or ctx.author
    
    c.execute("SELECT uses, fake, bonus, left FROM invites WHERE user_id = ?", (member.id,))
    result = c.fetchone()
    
    if result:
        uses, fake, bonus, left = result
        total = uses + bonus
        net = uses + bonus - left
        embed = discord.Embed(title="📨 Invite Statistics", color=discord.Color.green())
        embed.set_author(name=member.name, icon_url=member.avatar.url if member.avatar else None)
        embed.add_field(name="Total Invites", value=total, inline=True)
        embed.add_field(name="Real", value=uses, inline=True)
        embed.add_field(name="Fake", value=fake, inline=True)
        embed.add_field(name="Bonus", value=bonus, inline=True)
        embed.add_field(name="Left", value=left, inline=True)
        embed.add_field(name="Net", value=net, inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"{member.mention} has no invites recorded.")

@bot.command()
async def inv_leaderboard(ctx):
    """!inv_leaderboard - Shows top inviters"""
    c.execute("SELECT user_id, uses + bonus as total, uses, bonus, left FROM invites WHERE uses + bonus > 0 ORDER BY total DESC LIMIT 10")
    top = c.fetchall()
    
    if not top:
        await ctx.send("No invite data yet.")
        return
    
    embed = discord.Embed(title="🏆 Invite Leaderboard", color=discord.Color.gold())
    for i, (user_id, total, uses, bonus, left) in enumerate(top, 1):
        user = bot.get_user(user_id)
        name = user.name if user else f"User {user_id}"
        embed.add_field(name=f"{i}. {name}", value=f"Total: {total} (Real: {uses}, Bonus: {bonus}, Left: {left})", inline=False)
    
    await ctx.send(embed=embed)

@bot.command()
async def msg_leaderboard(ctx, days: int = 7):
    """!msg_leaderboard [days] - Shows top chatters (default 7 days)"""
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    c.execute("""
        SELECT user_id, SUM(count) as total 
        FROM messages 
        WHERE date >= ? 
        GROUP BY user_id 
        ORDER BY total DESC 
        LIMIT 10
    """, (start_date,))
    top = c.fetchall()
    
    if not top:
        await ctx.send("No message data yet.")
        return
    
    embed = discord.Embed(title=f"💬 Message Leaderboard (Last {days} days)", color=discord.Color.blue())
    for i, (user_id, total) in enumerate(top, 1):
        user = bot.get_user(user_id)
        name = user.name if user else f"User {user_id}"
        embed.add_field(name=f"{i}. {name}", value=f"{total} messages", inline=False)
    
    await ctx.send(embed=embed)

@bot.command()
async def voice_leaderboard(ctx, days: int = 7):
    """!voice_leaderboard [days] - Shows top voice users (default 7 days)"""
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    c.execute("""
        SELECT user_id, SUM(minutes) as total 
        FROM voice_activity 
        WHERE date >= ? 
        GROUP BY user_id 
        ORDER BY total DESC 
        LIMIT 10
    """, (start_date,))
    top = c.fetchall()
    
    if not top:
        await ctx.send("No voice data yet.")
        return
    
    embed = discord.Embed(title=f"🎙️ Voice Activity Leaderboard (Last {days} days)", color=discord.Color.purple())
    for i, (user_id, minutes) in enumerate(top, 1):
        user = bot.get_user(user_id)
        name = user.name if user else f"User {user_id}"
        hours = minutes // 60
        mins = minutes % 60
        embed.add_field(name=f"{i}. {name}", value=f"{hours}h {mins}m", inline=False)
    
    await ctx.send(embed=embed)

@bot.command()
async def scan(ctx, member: discord.Member = None):
    """!scan @user - Check if user has alt accounts (requires staff)"""
    if STAFF_ROLE_ID not in [r.id for r in ctx.author.roles]:
        await ctx.send("❌ Only staff can use this command.")
        return
    
    member = member or ctx.author
    
    # Get user IP from invites (same IP = possible alt)
    c.execute("""
        SELECT DISTINCT joiner_id 
        FROM invite_uses 
        WHERE joiner_id != ? 
        AND inviter_id IN (
            SELECT inviter_id FROM invite_uses WHERE joiner_id = ?
        )
    """, (member.id, member.id))
    possible_alts = c.fetchall()
    
    if possible_alts:
        alt_list = ", ".join([f"<@{alt[0]}>" for alt in possible_alts[:5]])
        await ctx.send(f"⚠️ Possible alt accounts for {member.mention}:\n{alt_list}")
    else:
        await ctx.send(f"✅ No alt accounts detected for {member.mention}")

@bot.command()
async def user_stats(ctx, member: discord.Member = None):
    """!user_stats @user - Show all stats for a user"""
    member = member or ctx.author
    
    # Messages
    c.execute("SELECT SUM(count) FROM messages WHERE user_id = ?", (member.id,))
    total_msgs = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(count) FROM messages WHERE user_id = ? AND date >= date('now', '-7 days')", (member.id,))
    weekly_msgs = c.fetchone()[0] or 0
    
    # Voice
    c.execute("SELECT SUM(minutes) FROM voice_activity WHERE user_id = ? AND date >= date('now', '-30 days')", (member.id,))
    voice_minutes = c.fetchone()[0] or 0
    
    # Invites
    c.execute("SELECT uses, bonus, left FROM invites WHERE user_id = ?", (member.id,))
    inv_result = c.fetchone()
    total_invites = inv_result[0] + inv_result[1] if inv_result else 0
    
    # Join date
    join_date = member.joined_at.strftime("%b %d, %Y")
    
    embed = discord.Embed(title=f"📊 Stats for {member.name}", color=discord.Color.blue())
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    embed.add_field(name="📅 Joined Server", value=join_date, inline=True)
    embed.add_field(name="💬 Total Messages", value=total_msgs, inline=True)
    embed.add_field(name="📨 Total Invites", value=total_invites, inline=True)
    embed.add_field(name="📈 Weekly Messages", value=weekly_msgs, inline=True)
    embed.add_field(name="🎙️ Voice (30d)", value=f"{voice_minutes // 60}h {voice_minutes % 60}m", inline=True)
    
    await ctx.send(embed=embed)

@bot.command()
async def alt_scan(ctx):
    """!alt_scan - Scan server for potential alt accounts (staff only)"""
    if STAFF_ROLE_ID not in [r.id for r in ctx.author.roles]:
        await ctx.send("❌ Only staff can use this command.")
        return
    
    await ctx.send("🔍 Scanning for alt accounts... This may take a moment.")
    
    # Find users with same IP (simplified - based on invite patterns)
    c.execute("""
        SELECT inviter_id, COUNT(DISTINCT joiner_id) as alts
        FROM invite_uses
        GROUP BY inviter_id
        HAVING alts > 1
        ORDER BY alts DESC
        LIMIT 10
    """)
    results = c.fetchall()
    
    if results:
        embed = discord.Embed(title="🔍 Potential Alt Account Detections", color=discord.Color.orange())
        for inviter_id, alts in results:
            embed.add_field(name=f"<@{inviter_id}>", value=f"{alts} possible alts", inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("✅ No alt accounts detected.")

@bot.command()
async def msg_today(ctx):
    """!msg_today - Show today's top chatters"""
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("""
        SELECT user_id, count 
        FROM messages 
        WHERE date = ? 
        ORDER BY count DESC 
        LIMIT 10
    """, (today,))
    top = c.fetchall()
    
    if not top:
        await ctx.send("No messages today yet.")
        return
    
    embed = discord.Embed(title="📊 Today's Top Chatters", color=discord.Color.blue())
    for i, (user_id, count) in enumerate(top, 1):
        user = bot.get_user(user_id)
        name = user.name if user else f"User {user_id}"
        embed.add_field(name=f"{i}. {name}", value=f"{count} messages", inline=False)
    
    await ctx.send(embed=embed)

# ========== SETUP COMMANDS ==========

@bot.command()
@commands.has_permissions(administrator=True)
async def set_stats_channel(ctx, channel: discord.TextChannel):
    """!set_stats_channel #channel - Set where stats are posted"""
    global STATS_CHANNEL_ID
    STATS_CHANNEL_ID = channel.id
    await ctx.send(f"✅ Stats will be posted in {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def set_log_channel(ctx, channel: discord.TextChannel):
    """!set_log_channel #channel - Set log channel"""
    global LOG_CHANNEL_ID
    LOG_CHANNEL_ID = channel.id
    await ctx.send(f"✅ Logs will be sent to {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def reset_stats(ctx):
    """!reset_stats - Reset all stats (admin only)"""
    c.execute("DELETE FROM messages")
    c.execute("DELETE FROM voice_activity")
    conn.commit()
    await ctx.send("✅ All stats have been reset.")

# ========== HELP COMMAND ==========

@bot.command()
async def stats_help(ctx):
    """!stats_help - Show all commands"""
    embed = discord.Embed(title="📊 Server Stats Bot Commands", color=discord.Color.blue())
    
    embed.add_field(
        name="📈 View Stats",
        value="`!stats` - Show server stats\n`!user_stats @user` - Show user stats\n`!msg_today` - Today's top chatters",
        inline=False
    )
    
    embed.add_field(
        name="🏆 Leaderboards",
        value="`!msg_leaderboard [days]` - Top chatters\n`!inv_leaderboard` - Top inviters\n`!voice_leaderboard [days]` - Top voice users",
        inline=False
    )
    
    embed.add_field(
        name="📨 Invites",
        value="`!invites @user` - Check user's invites\n`!scan @user` - Check for alts\n`!alt_scan` - Scan server for alts",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Admin",
        value="`!set_stats_channel #channel` - Set stats channel\n`!set_log_channel #channel` - Set log channel\n`!reset_stats` - Reset all stats",
        inline=False
    )
    
    await ctx.send(embed=embed)

# ========== RUN BOT ==========
@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online!")
    print(f"📊 Server Stats Bot loaded")
    update_stats.start()

bot.run(TOKEN)