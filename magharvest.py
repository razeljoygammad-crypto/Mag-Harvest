import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
from flask import Flask
from threading import Thread
import time
import sqlite3
import asyncio

# =========================================================
# FLASK SERVER FOR RENDER
# =========================================================
app = Flask(__name__)

@app.route("/")
def home():
    return "Farm Bot is online!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    thread = Thread(target=run_flask)
    thread.daemon = True
    thread.start()

# =========================================================
# FARM CONFIGURATION
# =========================================================
OWNER_USER_IDS = {
    923096413934616596,
    760023911764197396,
}

FARM_CHANNEL_ID = 1546817067464917022
ALLOWED_CATEGORY_ID = 1401449789983428719
FARM_DATABASE_FILE = "farm_bot.db"

TACKLE_EMOJI = discord.PartialEmoji(
    name="tackle",
    id=1548631058843697213,
    animated=False
)

SCIENCE_EMOJI = discord.PartialEmoji(
    name="science",
    id=1548631082822279268,
    animated=False
)

TACKLE_ROLE_IDS = {
    1401454637877297253,
    1401455558514577489,
}

SCIENCE_ROLE_IDS = {
    1401454637877297253,
    1401455558514577489,
}

TACKLE_TIME = 48 * 60 * 60
SCIENCE_TIME = 12 * 60 * 60

TACKLE_WORLDS = [
    "MAMAMOTACKLE",
    "TCKLSZ",
    "EVDYT",
]

SCIENCE_WORLDS = [
    "RGREG",
    "STROSTATS",
]

ALL_FARM_WORLDS = TACKLE_WORLDS + SCIENCE_WORLDS

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

farm_lock = asyncio.Lock()

def get_farm_db():
    return sqlite3.connect(
        FARM_DATABASE_FILE,
        timeout=30
    )
def initialize_farm_database():
    db = get_farm_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS farms (
            world TEXT PRIMARY KEY,
            farm_type TEXT NOT NULL,
            ready INTEGER NOT NULL DEFAULT 1,
            end_time REAL,
            panel_message_id INTEGER
        )
    """)
    cursor.execute("PRAGMA table_info(farms)")
    columns = {
        row[1]
        for row in cursor.fetchall()
    }
    if "panel_message_id" not in columns:
        print("⚠️ Old farm database detected.")
        print("🔧 Adding panel_message_id column...")
        cursor.execute("""
            ALTER TABLE farms
            ADD COLUMN panel_message_id INTEGER
        """)
        print("✅ Farm database upgraded successfully.")
    for world in TACKLE_WORLDS:
        cursor.execute("""
            INSERT OR IGNORE INTO farms
            (
                world,
                farm_type,
                ready,
                end_time,
                panel_message_id
            )
            VALUES (
                ?,
                'tackle',
                1,
                NULL,
                NULL
            )
        """, (world,))
    for world in SCIENCE_WORLDS:
        cursor.execute("""
            INSERT OR IGNORE INTO farms
            (
                world,
                farm_type,
                ready,
                end_time,
                panel_message_id
            )
            VALUES (
                ?,
                'science',
                1,
                NULL,
                NULL
            )
        """, (world,))
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_ping (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            message_id INTEGER
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO active_ping
        (id, message_id)
        VALUES (1, NULL)
    """)
    db.commit()
    db.close()
    print("✅ Farm database initialized.")
def get_farm(world):
    db = get_farm_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT
            farm_type,
            ready,
            end_time,
            panel_message_id
        FROM farms
        WHERE world = ?
    """, (world,))
    row = cursor.fetchone()
    db.close()
    if row is None:
        return {
            "farm_type": None,
            "ready": True,
            "end_time": None,
            "panel_message_id": None,
        }
    return {
        "farm_type": row[0],
        "ready": bool(row[1]),
        "end_time": row[2],
        "panel_message_id": row[3],
    }
def update_farm(
    world,
    ready,
    end_time,
    panel_message_id=None,
    update_message_id=False
):
    db = get_farm_db()
    cursor = db.cursor()
    if update_message_id:
        cursor.execute("""
            UPDATE farms
            SET
                ready = ?,
                end_time = ?,
                panel_message_id = ?
            WHERE world = ?
        """, (
            int(ready),
            end_time,
            panel_message_id,
            world
        ))
    else:
        cursor.execute("""
            UPDATE farms
            SET
                ready = ?,
                end_time = ?
            WHERE world = ?
        """, (
            int(ready),
            end_time,
            world
        ))
    db.commit()
    db.close()
def get_active_ping_id():
    db = get_farm_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT message_id
        FROM active_ping
        WHERE id = 1
    """)
    row = cursor.fetchone()
    db.close()
    if row is None:
        return None
    return row[0]
def set_active_ping_id(message_id):
    db = get_farm_db()
    cursor = db.cursor()
    cursor.execute("""
        UPDATE active_ping
        SET message_id = ?
        WHERE id = 1
    """, (message_id,))
    db.commit()
    db.close()
def clear_active_ping_id():
    db = get_farm_db()
    cursor = db.cursor()
    cursor.execute("""
        UPDATE active_ping
        SET message_id = NULL
        WHERE id = 1
    """)
    db.commit()
    db.close()
def get_spam_db():
    conn = sqlite3.connect(
        SPAM_DATABASE_FILE,
        timeout=30
    )
    conn.row_factory = sqlite3.Row
    return conn
def initialize_spam_database():
    conn = get_spam_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name = 'spam_worlds'
    """)
    table_exists = cursor.fetchone()
    if not table_exists:
        cursor.execute("""
            CREATE TABLE spam_worlds (
                world TEXT PRIMARY KEY,
                end_time_2h REAL,
                end_time_6h REAL,
                added_by INTEGER NOT NULL
            )
        """)
        print(
            "✅ New spam_worlds table created."
        )
    else:
        cursor.execute("""
            PRAGMA table_info(spam_worlds)
        """)
        columns = {
            row["name"]
            for row in cursor.fetchall()
        }
        if "end_time_2h" not in columns:
            cursor.execute("""
                ALTER TABLE spam_worlds
                ADD COLUMN end_time_2h REAL
            """)
            print(
                "✅ Added end_time_2h column."
            )
        if "end_time_6h" not in columns:
            cursor.execute("""
                ALTER TABLE spam_worlds
                ADD COLUMN end_time_6h REAL
            """)
            print(
                "✅ Added end_time_6h column."
            )
        if (
            "end_time" in columns
            and
            "duration_hours" in columns
        ):
            print(
                "🔄 Old spam timer data detected."
            )
            cursor.execute("""
                SELECT
                    world,
                    end_time,
                    duration_hours
                FROM spam_worlds
            """)
            old_rows = cursor.fetchall()
            for row in old_rows:
                world = row["world"]
                end_time = row["end_time"]
                duration = row["duration_hours"]
                if end_time is None:
                    continue
                if duration == 2:
                    cursor.execute("""
                        UPDATE spam_worlds
                        SET end_time_2h = ?
                        WHERE world = ?
                    """, (
                        end_time,
                        world
                    ))
                elif duration == 6:
                    cursor.execute("""
                        UPDATE spam_worlds
                        SET end_time_6h = ?
                        WHERE world = ?
                    """, (
                        end_time,
                        world
                    ))
            print(
                "✅ Old spam timer data migrated."
            )
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spam_panel (
            id INTEGER PRIMARY KEY,
            owner_id INTEGER,
            panel_message_id INTEGER
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO spam_panel
        (
            id,
            owner_id,
            panel_message_id
        )
        VALUES (
            1,
            NULL,
            NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spam_active_ping (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            message_id INTEGER
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO spam_active_ping
        (id, message_id)
        VALUES (1, NULL)
    """)
    conn.commit()
    conn.close()
    print(
        "✅ Spam database initialized."
    )
def is_owner(user_id):
    return user_id in OWNER_USER_IDS
def format_time(seconds):
    seconds = max(
        0,
        int(seconds)
    )
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    if days > 0:
        return (
            f"{days}d "
            f"{hours:02d}h "
            f"{minutes:02d}m "
            f"{seconds:02d}s"
        )
    return (
        f"{hours:02d}h "
        f"{minutes:02d}m "
        f"{seconds:02d}s"
    )
def is_allowed_farm_channel(channel):
    if channel is None:
        return False
    if channel.id != FARM_CHANNEL_ID:
        return False
    if channel.category_id != ALLOWED_CATEGORY_ID:
        return False
    return True
def get_farm_type(world):
    if world in TACKLE_WORLDS:
        return "tackle"
    if world in SCIENCE_WORLDS:
        return "science"
    return None
def get_timer(world):
    if world in TACKLE_WORLDS:
        return TACKLE_TIME
    if world in SCIENCE_WORLDS:
        return SCIENCE_TIME
    return 0
async def get_farm_channel():
    channel = bot.get_channel(
        FARM_CHANNEL_ID
    )
    if channel is not None:
        return channel
    try:
        return await bot.fetch_channel(
            FARM_CHANNEL_ID
        )
    except Exception as e:
        print(
            f"❌ Could not find farm channel: {e}"
        )
        return None
def get_world_status(world):
    farm = get_farm(world)
    if farm["ready"]:
        return "🟢 **READY**"
    if farm["end_time"] is None:
        return "🟢 **READY**"
    remaining = (
        farm["end_time"]
        - time.time()
    )
    if remaining <= 0:
        return "🟢 **READY**"
    return (
        f"⏳ `{format_time(remaining)}`"
    )
def tackle_embed():
    embed = discord.Embed(
        title=f"{TACKLE_EMOJI} TACKLE FARM",
        color=discord.Color.green()
    )
    description = (
        "Harvest the world, then click its "
        "**WORLDNAME** button.\n\n"
    )
    for world in TACKLE_WORLDS:
        description += (
            f"🌎 **{world}** → "
            f"{get_world_status(world)}\n"
        )
    description += (
        "\n⏱️ Harvest timer: **48 hours**"
    )
    embed.description = description
    return embed
def science_embed():
    embed = discord.Embed(
        title=f"{SCIENCE_EMOJI} SCIENCE STATION",
        color=discord.Color.blue()
    )
    description = (
        "Harvest the world, then click its "
        "**WORLDNAME** button.\n\n"
    )
    for world in SCIENCE_WORLDS:
        description += (
            f"🌎 **{world}** → "
            f"{get_world_status(world)}\n"
        )
    description += (
        "\n⏱️ Harvest timer: **12 hours**"
    )
    embed.description = description
    return embed
class TackleView(discord.ui.View):
    def __init__(
        self,
        ready_worlds=None
    ):
        super().__init__(
            timeout=None
        )
        if ready_worlds is None:
            ready_worlds = TACKLE_WORLDS
        for world in TACKLE_WORLDS:
            if world not in ready_worlds:
                continue
            button = discord.ui.Button(
                label=world,
                style=discord.ButtonStyle.green,
                emoji=TACKLE_EMOJI,
                custom_id=f"tackle_{world.lower()}"
            )
            async def callback(
                interaction,
                world=world
            ):
                await finish_world(
                    interaction,
                    world
                )
            button.callback = callback
            self.add_item(button)
class ScienceView(discord.ui.View):
    def __init__(
        self,
        ready_worlds=None
    ):
        super().__init__(
            timeout=None
        )
        if ready_worlds is None:
            ready_worlds = SCIENCE_WORLDS
        for world in SCIENCE_WORLDS:
            if world not in ready_worlds:
                continue
            button = discord.ui.Button(
                label=world,
                style=discord.ButtonStyle.blurple,
                emoji=SCIENCE_EMOJI,
                custom_id=f"science_{world.lower()}"
            )
            async def callback(
                interaction,
                world=world
            ):
                await finish_world(
                    interaction,
                    world
                )
            button.callback = callback
            self.add_item(button)
def get_ready_tackle_worlds():
    ready_worlds = []
    for world in TACKLE_WORLDS:
        farm = get_farm(world)
        if farm["ready"]:
            ready_worlds.append(world)
        elif (
            farm["end_time"] is not None
            and
            farm["end_time"] <= time.time()
        ):
            ready_worlds.append(world)
    return ready_worlds
def get_ready_science_worlds():
    ready_worlds = []
    for world in SCIENCE_WORLDS:
        farm = get_farm(world)
        if farm["ready"]:
            ready_worlds.append(world)
        elif (
            farm["end_time"] is not None
            and
            farm["end_time"] <= time.time()
        ):
            ready_worlds.append(world)
    return ready_worlds
async def finish_world(
    interaction,
    world
):
    if not is_allowed_farm_channel(
        interaction.channel
    ):
        await interaction.response.send_message(
            "❌ This button cannot be used here.",
            ephemeral=True
        )
        return
    await interaction.response.defer(
        ephemeral=True
    )
    async with farm_lock:
        farm = get_farm(world)
        if not farm["ready"]:
            if farm["end_time"] is not None:
                remaining = (
                    farm["end_time"]
                    - time.time()
                )
                if remaining > 0:
                    await interaction.followup.send(
                        f"⏳ **{world}** is already "
                        f"on cooldown.\n\n"
                        f"Next harvest: "
                        f"**{format_time(remaining)}**",
                        ephemeral=True
                    )
                    return
        timer = get_timer(world)
        end_time = (
            time.time()
            + timer
        )
        update_farm(
            world,
            ready=False,
            end_time=end_time
        )
    await update_farm_panels()
    await interaction.followup.send(
        f"✅ **{world}** timer started!\n"
        f"⏳ Next harvest in "
        f"**{format_time(timer)}**.",
        ephemeral=True
    )
async def update_tackle_panel():
    channel = await get_farm_channel()
    if channel is None:
        return
    if not is_allowed_farm_channel(channel):
        print(
            "❌ Farm channel/category does not match."
        )
        return
    message_id = None
    for world in TACKLE_WORLDS:
        farm = get_farm(world)
        if farm["panel_message_id"]:
            message_id = farm[
                "panel_message_id"
            ]
            break
    message = None
    if message_id:
        try:
            message = await channel.fetch_message(
                message_id
            )
        except discord.NotFound:
            message = None
        except Exception as e:
            print(
                f"❌ Tackle panel fetch error: {e}"
            )
    ready_worlds = get_ready_tackle_worlds()
    view = (
        TackleView(ready_worlds)
        if ready_worlds
        else None
    )
    if message is None:
        message = await channel.send(
            embed=tackle_embed(),
            view=view
        )
        for world in TACKLE_WORLDS:
            farm = get_farm(world)
            update_farm(
                world,
                ready=farm["ready"],
                end_time=farm["end_time"],
                panel_message_id=message.id,
                update_message_id=True
            )
        return
    await message.edit(
        embed=tackle_embed(),
        view=view
    )
async def update_science_panel():
    channel = await get_farm_channel()
    if channel is None:
        return
    if not is_allowed_farm_channel(channel):
        print(
            "❌ Farm channel/category does not match."
        )
        return
    message_id = None
    for world in SCIENCE_WORLDS:
        farm = get_farm(world)
        if farm["panel_message_id"]:
            message_id = farm[
                "panel_message_id"
            ]
            break
    message = None
    if message_id:
        try:
            message = await channel.fetch_message(
                message_id
            )
        except discord.NotFound:
            message = None
        except Exception as e:
            print(
                f"❌ Science panel fetch error: {e}"
            )
    ready_worlds = get_ready_science_worlds()
    view = (
        ScienceView(ready_worlds)
        if ready_worlds
        else None
    )
    if message is None:
        message = await channel.send(
            embed=science_embed(),
            view=view
        )
        for world in SCIENCE_WORLDS:
            farm = get_farm(world)
            update_farm(
                world,
                ready=farm["ready"],
                end_time=farm["end_time"],
                panel_message_id=message.id,
                update_message_id=True
            )
        return
    await message.edit(
        embed=science_embed(),
        view=view
    )
async def update_farm_panels():
    await update_tackle_panel()
    await update_science_panel()
async def delete_old_ping(channel):
    old_message_id = get_active_ping_id()
    if not old_message_id:
        return
    try:
        old_message = await channel.fetch_message(
            old_message_id
        )
        await old_message.delete()
        print(
            f"🗑️ Deleted previous harvest ping "
            f"({old_message_id})"
        )
    except discord.NotFound:
        print(
            "ℹ️ Previous harvest ping was already deleted."
        )
    except discord.Forbidden:
        print(
            "❌ Bot does not have permission "
            "to delete the previous ping."
        )
    except Exception as e:
        print(
            f"❌ Error deleting old ping: {e}"
        )
    finally:
        clear_active_ping_id()
async def send_harvest_ping(
    channel,
    world
):
    await delete_old_ping(channel)
    if world in TACKLE_WORLDS:
        role_ids = TACKLE_ROLE_IDS
        emoji = TACKLE_EMOJI
        farm_name = "Tackle Farm"
    else:
        role_ids = SCIENCE_ROLE_IDS
        emoji = SCIENCE_EMOJI
        farm_name = "Science Station"
    mentions = []
    for role_id in role_ids:
        role = channel.guild.get_role(
            role_id
        )
        if role:
            mentions.append(
                role.mention
            )
        else:
            print(
                f"❌ Role {role_id} not found."
            )
    content = ""
    if mentions:
        content = " ".join(mentions)
    content += (
        f"\n\n"
        f"{emoji} **{farm_name} is ready!**\n"
        f"🌎 World: **{world}**\n"
        f"🟢 **READY TO HARVEST!**"
    )
    message = await channel.send(
        content=content,
        allowed_mentions=discord.AllowedMentions(
            roles=True
        )
    )
    set_active_ping_id(
        message.id
    )
    print(
        f"🔔 New harvest ping sent for {world}"
    )
    print(
        f"🆔 Ping message ID: {message.id}"
    )
async def check_expired_farm_timers():
    channel = await get_farm_channel()
    if channel is None:
        return
    expired_worlds = []
    async with farm_lock:
        current_time = time.time()
        for world in ALL_FARM_WORLDS:
            farm = get_farm(world)
            if farm["ready"]:
                continue
            if farm["end_time"] is None:
                continue
            if current_time < farm["end_time"]:
                continue
            update_farm(
                world,
                ready=True,
                end_time=None
            )
            expired_worlds.append(world)
    for world in expired_worlds:
        await send_harvest_ping(
            channel,
            world
        )
@tasks.loop(seconds=10)
async def timer_loop():
    try:
        await check_expired_farm_timers()
        await update_farm_panels()
    except Exception as e:
        print(
            f"❌ Farm timer loop error: {e}"
        )
@timer_loop.before_loop
async def before_timer_loop():
    await bot.wait_until_ready()
@bot.tree.command(
    name="setup",
    description="Reset all farm timers and panels."
)
async def setup(
    interaction: discord.Interaction
):
    if not is_owner(
        interaction.user.id
    ):
        await interaction.response.send_message(
            "❌ **You don't have permission "
            "to use this command.**",
            ephemeral=True
        )
        return
    if not is_allowed_farm_channel(
        interaction.channel
    ):
        await interaction.response.send_message(
            "❌ This command can only be "
            "used in the configured farm channel.",
            ephemeral=True
        )
        return
    await interaction.response.defer()
    async with farm_lock:
        for world in ALL_FARM_WORLDS:
            farm = get_farm(world)
            update_farm(
                world,
                ready=True,
                end_time=None,
                panel_message_id=farm[
                    "panel_message_id"
                ],
                update_message_id=False
            )
    await update_farm_panels()
    await interaction.followup.send(
        "✅ **All farms have been reset.**"
    )
@bot.tree.command(
    name="settime",
    description="Set the current timer for a farm world."
)
@app_commands.describe(
    world="The farm world",
    hours="How many hours the current timer should have"
)
@app_commands.choices(
    world=[
        app_commands.Choice(
            name="MAMAMOTACKLE",
            value="MAMAMOTACKLE"
        ),
        app_commands.Choice(
            name="TCKLSZ",
            value="TCKLSZ"
        ),
        app_commands.Choice(
            name="EVDYT",
            value="EVDYT"
        ),
        app_commands.Choice(
            name="RGREG",
            value="RGREG"
        ),
        app_commands.Choice(
            name="STROSTATS",
            value="STROSTATS"
        ),
    ]
)
async def settime(
    interaction: discord.Interaction,
    world: app_commands.Choice[str],
    hours: float
):
    if not is_owner(
        interaction.user.id
    ):
        await interaction.response.send_message(
            "❌ **You don't have permission "
            "to use this command.**",
            ephemeral=True
        )
        return
    if not is_allowed_farm_channel(
        interaction.channel
    ):
        await interaction.response.send_message(
            "❌ This command can only be "
            "used in the configured farm channel.",
            ephemeral=True
        )
        return
    world = world.value
    if hours <= 0:
        await interaction.response.send_message(
            "❌ The number of hours must be "
            "greater than 0.",
            ephemeral=True
        )
        return
    seconds = int(
        hours * 60 * 60
    )
    end_time = (
        time.time()
        + seconds
    )
    async with farm_lock:
        update_farm(
            world,
            ready=False,
            end_time=end_time
        )
    await update_farm_panels()
    await interaction.response.send_message(
        f"✅ **{world}** timer set to "
        f"**{format_time(seconds)}** remaining.\n\n"
        f"⏱️ This only changes the **current cycle**.\n"
        f"🔄 The next normal Finish will use the "
        f"regular timer.",
        ephemeral=True
    )
@bot.tree.command(
    name="status",
    description="Show the current status of all farms."
)
async def status(
    interaction: discord.Interaction
):
    if not is_owner(
        interaction.user.id
    ):
        await interaction.response.send_message(
            "❌ **You don't have permission "
            "to use this command.**",
            ephemeral=True
        )
        return
    if not is_allowed_farm_channel(
        interaction.channel
    ):
        await interaction.response.send_message(
            "❌ This command can only be "
            "used in the configured farm channel.",
            ephemeral=True
        )
        return
    embed = discord.Embed(
        title="🌾 Farm Status",
        color=discord.Color.blurple()
    )
    tackle_text = ""
    for world in TACKLE_WORLDS:
        tackle_text += (
            f"{TACKLE_EMOJI} `{world}` → "
            f"{get_world_status(world)}\n"
        )
    embed.add_field(
        name=f"{TACKLE_EMOJI} Tackle — 48 Hours",
        value=tackle_text,
        inline=False
    )
    science_text = ""
    for world in SCIENCE_WORLDS:
        science_text += (
            f"{SCIENCE_EMOJI} `{world}` → "
            f"{get_world_status(world)}\n"
        )
    embed.add_field(
        name=f"{SCIENCE_EMOJI} Science Station — 12 Hours",
        value=science_text,
        inline=False
    )
    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )

@bot.event
async def on_ready():
    print("===================================")
    print(f"Logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("===================================")

    initialize_farm_database()

    if not hasattr(bot, "_farm_views_registered"):
        bot.add_view(TackleView())
        bot.add_view(ScienceView())
        bot._farm_views_registered = True
        print("Persistent farm buttons registered.")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} farm slash commands.")
    except Exception as e:
        print(f"Slash command sync error: {e}")

    await check_expired_farm_timers()
    await update_farm_panels()

    if not timer_loop.is_running():
        timer_loop.start()
        print("Farm timer loop started.")

    print("🌾 Farm system is running!")
    print("🎯 Tackle: 3 worlds / 48 hours")
    print("🔬 Science: 2 worlds / 12 hours")
    print("🔔 Farm: ONE active harvest ping")
    print("===================================")

# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    keep_alive()
    bot.run(os.getenv("TOKEN"))

