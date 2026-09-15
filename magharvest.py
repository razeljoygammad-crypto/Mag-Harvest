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
    app.run(
        host="0.0.0.0",
        port=port
    )
def keep_alive():
    thread = Thread(target=run_flask)
    thread.daemon = True
    thread.start()
OWNER_USER_IDS = {
    923096413934616596,
    760023911764197396,
}
FARM_CHANNEL_ID = 1546817067464917022
ALLOWED_CATEGORY_ID = 1401449789983428719
FARM_DATABASE_FILE = "farm_bot.db"
TACKLE_EMOJI = discord.PartialEmoji(name="tackle", id=1548631058843697213, animated=False)
SCIENCE_EMOJI = discord.PartialEmoji(name="science", id=1548631082822279268, animated=False)
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
ALL_FARM_WORLDS = (
    TACKLE_WORLDS
    + SCIENCE_WORLDS
)
SPAM_CHANNEL_ID = 1548670456385765426
SPAM_DATABASE_FILE = "spam_bot.db"
TWO_HOURS = 2 * 60 * 60 + 10 * 60  # 2 hours 10 minutes
SIX_HOURS = 6 * 60 * 60
SPAM_SHORT_LABEL = "2H 10M"
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(
    command_prefix="!",
    intents=intents
)
farm_lock = asyncio.Lock()
spam_lock = asyncio.Lock()
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
def normalize_world(world):
    return world.strip().upper()
def add_spam_world(
    world,
    user_id
):
    world = normalize_world(world)
    conn = get_spam_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO spam_worlds
        (
            world,
            end_time_2h,
            end_time_6h,
            added_by
        )
        VALUES (
            ?,
            NULL,
            NULL,
            ?
        )
    """, (
        world,
        user_id
    ))
    conn.commit()
    conn.close()
def remove_spam_world(world):
    world = normalize_world(world)
    conn = get_spam_db()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM spam_worlds
        WHERE world = ?
    """, (
        world,
    ))
    removed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return removed
def get_spam_world(world):
    world = normalize_world(world)
    conn = get_spam_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *
        FROM spam_worlds
        WHERE world = ?
    """, (
        world,
    ))
    row = cursor.fetchone()
    conn.close()
    return row
def get_all_spam_worlds():
    conn = get_spam_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *
        FROM spam_worlds
        ORDER BY world ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows
def start_spam_timer(
    world,
    duration_hours
):
    world = normalize_world(world)
    if duration_hours == 2:
        end_time = (
            time.time()
            + TWO_HOURS
        )
    elif duration_hours == 6:
        end_time = (
            time.time()
            + SIX_HOURS
        )
    else:
        return
    conn = get_spam_db()
    cursor = conn.cursor()
    if duration_hours == 2:
        cursor.execute("""
            UPDATE spam_worlds
            SET end_time_2h = ?
            WHERE world = ?
        """, (
            end_time,
            world
        ))
    elif duration_hours == 6:
        cursor.execute("""
            UPDATE spam_worlds
            SET end_time_6h = ?
            WHERE world = ?
        """, (
            end_time,
            world
        ))
    conn.commit()
    conn.close()
def clear_spam_timer(
    world,
    duration_hours
):
    world = normalize_world(world)
    conn = get_spam_db()
    cursor = conn.cursor()
    if duration_hours == 2:
        cursor.execute("""
            UPDATE spam_worlds
            SET end_time_2h = NULL
            WHERE world = ?
        """, (
            world,
        ))
    elif duration_hours == 6:
        cursor.execute("""
            UPDATE spam_worlds
            SET end_time_6h = NULL
            WHERE world = ?
        """, (
            world,
        ))
    conn.commit()
    conn.close()
def reset_all_spam_timers():
    conn = get_spam_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE spam_worlds
        SET
            end_time_2h = NULL,
            end_time_6h = NULL
    """)
    conn.commit()
    conn.close()
def get_spam_active_ping_id():
    conn = get_spam_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT message_id
        FROM spam_active_ping
        WHERE id = 1
    """)
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return row[0]

def set_spam_active_ping_id(message_id):
    conn = get_spam_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE spam_active_ping
        SET message_id = ?
        WHERE id = 1
    """, (message_id,))
    conn.commit()
    conn.close()

def clear_spam_active_ping_id():
    conn = get_spam_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE spam_active_ping
        SET message_id = NULL
        WHERE id = 1
    """)
    conn.commit()
    conn.close()

async def delete_old_spam_ping(channel):
    old_message_id = get_spam_active_ping_id()
    if not old_message_id:
        return
    try:
        old_message = await channel.fetch_message(old_message_id)
        await old_message.delete()
        print(f"🗑️ Deleted previous Spam ready ping ({old_message_id})")
    except discord.NotFound:
        print("ℹ️ Previous Spam ready ping was already deleted.")
    except discord.Forbidden:
        print("❌ Bot does not have permission to delete the previous Spam ping.")
    except Exception as e:
        print(f"❌ Error deleting old Spam ping: {e}")
    finally:
        clear_spam_active_ping_id()

async def send_spam_ready_ping(channel, world, owner_id, duration):
    await delete_old_spam_ping(channel)
    label = SPAM_SHORT_LABEL if duration == 2 else "6 HOURS"
    try:
        message = await channel.send(
            f"🔔 <@{owner_id}> "
            f"**{world}** — "
            f"**{label}** timer is ready!"
        )
        set_spam_active_ping_id(message.id)
        print(f"🔔 New Spam ready ping sent for {world} ({label})")
        print(f"🆔 Spam ping message ID: {message.id}")
    except Exception as e:
        print(f"❌ Error sending Spam ready ping: {e}")

def get_spam_panel():
    conn = get_spam_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *
        FROM spam_panel
        WHERE id = 1
    """)
    row = cursor.fetchone()
    conn.close()
    return row
def save_spam_panel(
    owner_id,
    message_id
):
    conn = get_spam_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE spam_panel
        SET
            owner_id = ?,
            panel_message_id = ?
        WHERE id = 1
    """, (
        owner_id,
        message_id
    ))
    conn.commit()
    conn.close()
def clear_spam_panel_message():
    conn = get_spam_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE spam_panel
        SET panel_message_id = NULL
        WHERE id = 1
    """)
    conn.commit()
    conn.close()
def is_allowed_spam_channel(channel):
    if channel is None:
        return False
    return channel.id == SPAM_CHANNEL_ID
def format_spam_countdown(end_time):
    if end_time is None:
        return "🟢 **READY**"
    remaining = end_time - time.time()
    if remaining <= 0:
        return "🟢 **READY**"
    # Exactly the same countdown style used by the Farm/Tackle system.
    return f"⏳ `{format_time(remaining)}`"
def spam_embed():
    embed = discord.Embed(
        title="📢 SPAM TIMER",
        description=(
            "Select a world below to manage its timers.\n\n"
            "🌎 **World Owner**\n"
            "The user who added the world controls its timers.\n\n"
            "⏱️ **Independent Timers**\n"
            "The 2H 10M and 6-hour timers can run "
            "at the same time."
        ),
        color=discord.Color.blurple()
    )

    worlds = get_all_spam_worlds()
    if not worlds:
        embed.add_field(
            name="🌎 WORLDS",
            value="No worlds have been added yet.",
            inline=False
        )
        embed.set_footer(
            text="Use /spamadd to add a world"
        )
        return embed

    description = ""
    for row in worlds:
        world = row["world"]
        owner = f"<@{row['added_by']}>"
        description += (
            f"🌎 **{world}** — {owner}\n"
            f"⏱️ **2H 10M** → {format_spam_countdown(row['end_time_2h'])}\n"
            f"⏱️ **6H** → {format_spam_countdown(row['end_time_6h'])}\n\n"
        )

    description = description.rstrip()
    if len(description) > 4096:
        description = description[:4090] + "..."

    embed.description = description
    embed.set_footer(
        text="Use /spamadd to add a world"
    )
    return embed

class TimerChoiceView(
    discord.ui.View
):
    def __init__(
        self,
        world,
        owner_id
    ):
        super().__init__(
            timeout=300
        )
        self.world = world
        self.owner_id = owner_id
    async def interaction_check(
        self,
        interaction
    ):
        if interaction.channel_id != SPAM_CHANNEL_ID:
            await interaction.response.send_message(
                "❌ You cannot use this panel here.",
                ephemeral=True
            )
            return False
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                (
                    "❌ Only the person who added "
                    "this world can start its timers."
                ),
                ephemeral=True
            )
            return False
        return True
    @discord.ui.button(
        label="2H 10M",
        emoji="⏱️",
        style=discord.ButtonStyle.success
    )
    async def two_hours(
        self,
        interaction,
        button
    ):
        await start_spam_world_timer(
            interaction,
            self.world,
            self.owner_id,
            2
        )
    @discord.ui.button(
        label="6 HOURS",
        emoji="⏱️",
        style=discord.ButtonStyle.primary
    )
    async def six_hours(
        self,
        interaction,
        button
    ):
        await start_spam_world_timer(
            interaction,
            self.world,
            self.owner_id,
            6
        )
async def start_spam_world_timer(
    interaction,
    world,
    owner_id,
    duration_hours
):
    world = normalize_world(world)
    try:
        await interaction.response.defer(
            ephemeral=True
        )
    except discord.InteractionResponded:
        pass
    row = get_spam_world(world)
    if row is None:
        await interaction.edit_original_response(
            content="❌ This world no longer exists."
        )
        return
    if row["added_by"] != interaction.user.id:
        await interaction.edit_original_response(
            content=(
                "❌ Only the person who added "
                "this world can start its timer."
            )
        )
        return
    if owner_id != interaction.user.id:
        await interaction.edit_original_response(
            content=(
                "❌ You are not the owner "
                "of this world."
            )
        )
        return
    if duration_hours == 2:
        current_end = row["end_time_2h"]
    else:
        current_end = row["end_time_6h"]
    if current_end is not None:
        remaining = (
            current_end
            - time.time()
        )
        if remaining > 0:
            await interaction.edit_original_response(
                content=(
                    f"⏳ **{world} — "
                    f"{SPAM_SHORT_LABEL if duration_hours == 2 else '6 HOURS'}** "
                    "is already running.\n\n"
                    f"Time remaining: "
                    f"**{format_time(remaining)}**\n\n"
                    "You can still use the other timer."
                )
            )
            return
        clear_spam_timer(
            world,
            duration_hours
        )
    start_spam_timer(
        world,
        duration_hours
    )
    await interaction.edit_original_response(
        content=(
            f"✅ **{world}** started for "
            f"**{SPAM_SHORT_LABEL if duration_hours == 2 else '6 hours'}**.\n\n"
            "⏱️ This timer is running independently.\n"
            "You can still start the other timer."
        )
    )
    await update_spam_panel()
class WorldSelect(
    discord.ui.Select
):
    def __init__(self):
        worlds = get_all_spam_worlds()
        options = []
        for row in worlds[:25]:
            options.append(
                discord.SelectOption(
                    label=row["world"][:100],
                    description=(
                        f"Owner: User "
                        f"{row['added_by']}"
                    )[:100],
                    value=row["world"]
                )
            )
        if not options:
            options.append(
                discord.SelectOption(
                    label="No worlds available",
                    description=(
                        "Use /spamadd first."
                    ),
                    value="__none__"
                )
            )
        super().__init__(
            placeholder="🌎 Select a world...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="spam_world_select"
        )
    async def callback(
        self,
        interaction
    ):
        if interaction.channel_id != SPAM_CHANNEL_ID:
            await interaction.response.send_message(
                "❌ You cannot use this panel here.",
                ephemeral=True
            )
            return
        await interaction.response.defer(
            ephemeral=True
        )
        world = normalize_world(
            self.values[0]
        )
        if world == "__NONE__":
            await interaction.edit_original_response(
                content=(
                    "❌ No worlds have been added yet."
                )
            )
            return
        row = get_spam_world(world)
        if row is None:
            await interaction.edit_original_response(
                content=(
                    "❌ This world no longer exists."
                )
            )
            return
        owner_id = row["added_by"]
        if interaction.user.id == owner_id:
            content = (
                f"🌎 **{world}**\n\n"
                "Choose a timer.\n\n"
                f"⏱️ **{SPAM_SHORT_LABEL}** and **6 HOURS** "
                "are independent.\n\n"
                "You can run both at the same time."
            )
        else:
            content = (
                f"🌎 **{world}**\n\n"
                f"👤 Owner: <@{owner_id}>\n\n"
                "You can view the timer options, "
                "but only the owner can start them."
            )
        await interaction.edit_original_response(
            content=content,
            view=TimerChoiceView(
                world,
                owner_id
            )
        )
class SpamView(
    discord.ui.View
):
    def __init__(self):
        super().__init__(
            timeout=None
        )
        self.add_item(
            WorldSelect()
        )
async def update_spam_panel():
    panel = get_spam_panel()
    if panel is None:
        return
    message_id = panel[
        "panel_message_id"
    ]
    if not message_id:
        return
    channel = bot.get_channel(
        SPAM_CHANNEL_ID
    )
    if channel is None:
        try:
            channel = await bot.fetch_channel(
                SPAM_CHANNEL_ID
            )
        except Exception as e:
            print(
                f"❌ Error fetching Spam channel: {e}"
            )
            return
    try:
        message = await channel.fetch_message(
            message_id
        )
    except discord.NotFound:
        clear_spam_panel_message()
        return
    except Exception as e:
        print(
            f"❌ Error fetching Spam panel: {e}"
        )
        return
    try:
        await message.edit(
            embed=spam_embed(),
            view=SpamView()
        )
    except Exception as e:
        print(
            f"❌ Error updating Spam panel: {e}"
        )
@bot.tree.command(
    name="spamsetup",
    description="Create or update the Spam Timer panel"
)
async def spamsetup(
    interaction: discord.Interaction
):
    if interaction.user.id not in OWNER_USER_IDS:
        await interaction.response.send_message(
            "❌ You are not allowed to use this command.",
            ephemeral=True
        )
        return
    if not is_allowed_spam_channel(
        interaction.channel
    ):
        await interaction.response.send_message(
            "❌ Use `/spamsetup` in the configured Spam channel.",
            ephemeral=True
        )
        return
    await interaction.response.defer(
        ephemeral=True
    )
    panel = get_spam_panel()
    message_id = panel[
        "panel_message_id"
    ]
    if message_id:
        try:
            message = await interaction.channel.fetch_message(
                message_id
            )
            await message.edit(
                embed=spam_embed(),
                view=SpamView()
            )
            await interaction.edit_original_response(
                content="✅ Existing Spam panel updated."
            )
            return
        except discord.NotFound:
            clear_spam_panel_message()
        except Exception as e:
            print(
                f"❌ Panel error: {e}"
            )
    message = await interaction.channel.send(
        embed=spam_embed(),
        view=SpamView()
    )
    save_spam_panel(
        interaction.user.id,
        message.id
    )
    await interaction.edit_original_response(
        content="✅ Spam panel created."
    )
@bot.tree.command(
    name="spamadd",
    description="Add a Spam world"
)
@app_commands.describe(
    world="The world name to add"
)
async def spamadd(
    interaction: discord.Interaction,
    world: str
):
    if not is_allowed_spam_channel(
        interaction.channel
    ):
        await interaction.response.send_message(
            "❌ Use `/spamadd` in the configured Spam channel.",
            ephemeral=True
        )
        return
    world = normalize_world(world)
    if len(world) > 100:
        await interaction.response.send_message(
            "❌ World name is too long.",
            ephemeral=True
        )
        return
    existing = get_spam_world(world)
    if existing:
        if existing["added_by"] == interaction.user.id:
            await interaction.response.send_message(
                f"❌ You already added **{world}**.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ **{world}** was already added by another user.",
                ephemeral=True
            )
        return
    add_spam_world(
        world,
        interaction.user.id
    )
    await interaction.response.send_message(
        f"✅ **{world}** has been added.\n"
        f"👤 Owner: {interaction.user.mention}\n\n"
        "You can now use both the 2H 10M and 6-hour timers.",
        ephemeral=True
    )
    await update_spam_panel()
@bot.tree.command(
    name="spamremove",
    description="Remove a Spam world"
)
@app_commands.describe(
    world="The world to remove"
)
async def spamremove(
    interaction: discord.Interaction,
    world: str
):
    if interaction.user.id not in OWNER_USER_IDS:
        await interaction.response.send_message(
            "❌ Only the bot owner can remove worlds.",
            ephemeral=True
        )
        return
    if not is_allowed_spam_channel(
        interaction.channel
    ):
        await interaction.response.send_message(
            "❌ Use `/spamremove` in the configured Spam channel.",
            ephemeral=True
        )
        return
    world = normalize_world(world)
    if not remove_spam_world(world):
        await interaction.response.send_message(
            f"❌ **{world}** does not exist.",
            ephemeral=True
        )
        return
    await interaction.response.send_message(
        f"✅ **{world}** has been removed.",
        ephemeral=True
    )
    await update_spam_panel()
@bot.tree.command(
    name="spamreset",
    description="Reset a world's timers"
)
@app_commands.describe(
    world="World name, or 'all' for every world"
)
async def spamreset(
    interaction: discord.Interaction,
    world: str
):
    if not is_allowed_spam_channel(
        interaction.channel
    ):
        await interaction.response.send_message(
            "❌ Use `/spamreset` in the configured Spam channel.",
            ephemeral=True
        )
        return
    world = normalize_world(world)
    if world == "ALL":
        if interaction.user.id not in OWNER_USER_IDS:
            await interaction.response.send_message(
                "❌ Only the bot owner can reset all worlds.",
                ephemeral=True
            )
            return
        reset_all_spam_timers()
        await interaction.response.send_message(
            "✅ Both timers for all worlds have been reset.",
            ephemeral=True
        )
        await update_spam_panel()
        return
    row = get_spam_world(world)
    if row is None:
        await interaction.response.send_message(
            f"❌ **{world}** does not exist.",
            ephemeral=True
        )
        return
    world_owner_id = row["added_by"]
    if interaction.user.id in OWNER_USER_IDS:
        allowed = True
    elif interaction.user.id == world_owner_id:
        allowed = True
    else:
        allowed = False
    if not allowed:
        await interaction.response.send_message(
            "❌ You can only reset a world that you added.",
            ephemeral=True
        )
        return
    clear_spam_timer(
        world,
        2
    )
    clear_spam_timer(
        world,
        6
    )
    await interaction.response.send_message(
        f"✅ Both timers for **{world}** have been reset.",
        ephemeral=True
    )
    await update_spam_panel()
@bot.tree.command(
    name="spamstatus",
    description="Show Spam Timer status"
)
async def spamstatus(
    interaction: discord.Interaction
):
    if interaction.user.id not in OWNER_USER_IDS:
        await interaction.response.send_message(
            "❌ Only the bot owner can use this command.",
            ephemeral=True
        )
        return
    if not is_allowed_spam_channel(
        interaction.channel
    ):
        await interaction.response.send_message(
            "❌ Use `/spamstatus` in the configured Spam channel.",
            ephemeral=True
        )
        return
    worlds = get_all_spam_worlds()
    now = time.time()
    total = len(worlds)
    running_2h = 0
    running_6h = 0
    lines = []
    for row in worlds:
        world = row["world"]
        end_2h = row["end_time_2h"]
        if end_2h is not None:
            remaining_2h = (
                end_2h - now
            )
            if remaining_2h > 0:
                running_2h += 1
                lines.append(
                    f"⏱️ **{world}** — "
                    f"{SPAM_SHORT_LABEL}: {format_time(remaining_2h)}"
                )
        end_6h = row["end_time_6h"]
        if end_6h is not None:
            remaining_6h = (
                end_6h - now
            )
            if remaining_6h > 0:
                running_6h += 1
                lines.append(
                    f"⏱️ **{world}** — "
                    f"6H: {format_time(remaining_6h)}"
                )
    embed = discord.Embed(
        title="📊 SPAM STATUS",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="🌎 Worlds",
        value=str(total),
        inline=True
    )
    embed.add_field(
        name=f"⏱️ {SPAM_SHORT_LABEL} Running",
        value=str(running_2h),
        inline=True
    )
    embed.add_field(
        name="⏱️ 6H Running",
        value=str(running_6h),
        inline=True
    )
    if lines:
        text = "\n".join(lines)
        if len(text) > 1024:
            text = text[:1020] + "..."
        embed.add_field(
            name="Currently Running",
            value=text,
            inline=False
        )
    else:
        embed.add_field(
            name="Currently Running",
            value="No timers are running.",
            inline=False
        )
    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )
@bot.tree.command(
    name="spamtimer",
    description="Set the current timer for a Spam world."
)
@app_commands.describe(
    world="The Spam world",
    hours="How many hours the current timer should have"
)
async def spamtimer(
    interaction: discord.Interaction,
    world: str,
    hours: float
):
    if interaction.user.id not in OWNER_USER_IDS:
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.",
            ephemeral=True
        )
        return

    if not is_allowed_spam_channel(
        interaction.channel
    ):
        await interaction.response.send_message(
            "❌ This command can only be used in the configured Spam channel.",
            ephemeral=True
        )
        return

    world = normalize_world(world)

    if hours <= 0:
        await interaction.response.send_message(
            "❌ The number of hours must be greater than 0.",
            ephemeral=True
        )
        return

    row = get_spam_world(world)

    if row is None:
        await interaction.response.send_message(
            f"❌ **{world}** does not exist.",
            ephemeral=True
        )
        return

    seconds = int(hours * 60 * 60)
    end_time = time.time() + seconds

    conn = sqlite3.connect(
        SPAM_DATABASE_FILE
    )
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE spam_worlds
        SET end_time_2h = ?,
            end_time_6h = NULL
        WHERE world = ?
        """,
        (
            end_time,
            world
        )
    )

    conn.commit()
    conn.close()

    await update_spam_panel()

    await interaction.response.send_message(
        f"✅ **{world}** timer set to **{format_time(seconds)}**.\n\n"
        f"⏱️ This only changes the **current cycle**.",
        ephemeral=True
    )

@bot.tree.command(
    name="spamlist",
    description="List all Spam worlds and timers"
)
async def spamlist(
    interaction: discord.Interaction
):
    if not is_allowed_spam_channel(
        interaction.channel
    ):
        await interaction.response.send_message(
            "❌ Use `/spamlist` in the configured Spam channel.",
            ephemeral=True
        )
        return
    worlds = get_all_spam_worlds()
    if not worlds:
        await interaction.response.send_message(
            "🌎 No worlds have been added.",
            ephemeral=True
        )
        return
    now = time.time()
    lines = []
    for row in worlds:
        world = row["world"]
        owner = f"<@{row['added_by']}>"
        end_2h = row["end_time_2h"]
        timer_2h = format_spam_countdown(end_2h)

        end_6h = row["end_time_6h"]
        timer_6h = format_spam_countdown(end_6h)
        lines.append(
            f"**{world}** — {owner}\n"
            f"  ⏱️ {SPAM_SHORT_LABEL}: {timer_2h}\n"
            f"  ⏱️ 6H: {timer_6h}"
        )
    description = "\n\n".join(lines)
    if len(description) > 4096:
        description = (
            description[:4090]
            + "..."
        )
    embed = discord.Embed(
        title="🌎 SPAM WORLDS",
        description=description,
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )
@tasks.loop(seconds=10)
async def spam_timer_loop():
    try:
        worlds = get_all_spam_worlds()
        now = time.time()
        expired = []
        for row in worlds:
            world = row["world"]
            owner_id = row["added_by"]
            end_2h = row["end_time_2h"]
            if (
                end_2h is not None
                and
                end_2h <= now
            ):
                expired.append(
                    (
                        world,
                        owner_id,
                        2
                    )
                )
            end_6h = row["end_time_6h"]
            if (
                end_6h is not None
                and
                end_6h <= now
            ):
                expired.append(
                    (
                        world,
                        owner_id,
                        6
                    )
                )
        for (
            world,
            owner_id,
            duration
        ) in expired:
            clear_spam_timer(
                world,
                duration
            )
            channel = bot.get_channel(
                SPAM_CHANNEL_ID
            )
            if channel is None:
                try:
                    channel = await bot.fetch_channel(
                        SPAM_CHANNEL_ID
                    )
                except Exception as e:
                    print(
                        f"❌ Could not fetch Spam channel: {e}"
                    )
                    continue
            await send_spam_ready_ping(
                channel,
                world,
                owner_id,
                duration
            )
        # Keep the Spam panel countdown updated even when no timer expires.
        # This makes the displayed countdown decrease every loop (10 seconds).
        await update_spam_panel()
    except Exception as e:
        print(
            f"❌ Spam timer loop error: {e}"
        )
@spam_timer_loop.before_loop
async def before_spam_timer_loop():
    await bot.wait_until_ready()
@bot.event
async def on_ready():
    print(
        "==================================="
    )
    print(
        f"✅ Logged in as {bot.user}"
    )
    print(
        f"🆔 Bot ID: {bot.user.id}"
    )
    print(
        "==================================="
    )
    initialize_farm_database()
    initialize_spam_database()
    if not hasattr(
        bot,
        "_farm_views_registered"
    ):
        bot.add_view(
            TackleView()
        )
        bot.add_view(
            ScienceView()
        )
        bot._farm_views_registered = True
        print(
            "✅ Persistent farm buttons registered."
        )
    if not hasattr(
        bot,
        "_spam_view_registered"
    ):
        bot.add_view(
            SpamView()
        )
        bot._spam_view_registered = True
        print(
            "✅ Persistent Spam panel registered."
        )
    try:
        synced = await bot.tree.sync()
        print(
            f"✅ Synced {len(synced)} slash commands."
        )
    except Exception as e:
        print(
            f"❌ Slash command sync error: {e}"
        )
    await check_expired_farm_timers()
    await update_farm_panels()
    await update_spam_panel()
    if not timer_loop.is_running():
        timer_loop.start()
        print(
            "✅ Farm timer loop started."
        )
    if not spam_timer_loop.is_running():
        spam_timer_loop.start()
        print(
            "✅ Spam timer loop started."
        )
    print(
        "🌾 Farm system is running!"
    )
    print(
        "🎯 Tackle: 3 worlds / 48 hours"
    )
    print(
        "🔬 Science: 2 worlds / 12 hours"
    )
    print(
        "🔔 Farm: ONE active harvest ping"
    )
    print(
        "📢 Spam system is running!"
    )
    print(
        "⏱️ Spam: independent 2H 10M / 6H timers"
    )
    print(
        "==================================="
    )
# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    keep_alive()
    bot.run(
        os.getenv("TOKEN")
    )
