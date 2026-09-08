import discord
from discord.ext import commands, tasks
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

# =========================================================
# CONFIGURATION
# =========================================================

# Only these users can use !setup and !status
OWNER_USER_IDS = {
    923096413934616596,
    760023911764197396,
}

# Allowed category
ALLOWED_CATEGORY_ID = 1401449789983428719

# Farm channel
CHANNEL_ID = 1546817067464917022


# =========================================================
# ROLES
# =========================================================

# Roles that will be pinged for TACKLE
TACKLE_ROLE_IDS = {
    1401454637877297253,
    1401455558514577489,
}

# Roles that will be pinged for SCIENCE
SCIENCE_ROLE_IDS = {
    1401454637877297253,
    1401455558514577489,
}


# =========================================================
# TIMER SETTINGS
# =========================================================

# Tackle = 48 hours
TACKLE_TIME = 48 * 60 * 60

# Science = 10 hours
SCIENCE_TIME = 12 * 60 * 60


# =========================================================
# WORLDS
# =========================================================

TACKLE_WORLDS = [
    "MAMAMOTACKLE",
    "TCKLSZ",
    "EVDYT",
]

SCIENCE_WORLDS = [
    "RGREG",
    "STROSTATS",
]

ALL_WORLDS = TACKLE_WORLDS + SCIENCE_WORLDS


# =========================================================
# DATABASE
# =========================================================

DATABASE_FILE = "farm_bot.db"


def get_db():
    return sqlite3.connect(
        DATABASE_FILE,
        timeout=30
    )


def initialize_database():
    """
    Creates the database if it doesn't exist.

    Also automatically upgrades an old database
    by adding panel_message_id if necessary.
    """

    db = get_db()
    cursor = db.cursor()

    # -----------------------------------------------------
    # Create table if it doesn't exist
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS farms (
            world TEXT PRIMARY KEY,
            farm_type TEXT NOT NULL,
            ready INTEGER NOT NULL DEFAULT 1,
            end_time REAL,
            panel_message_id INTEGER
        )
    """)

    # -----------------------------------------------------
    # CHECK EXISTING COLUMNS
    # -----------------------------------------------------

    cursor.execute("PRAGMA table_info(farms)")
    columns = {
        row[1]
        for row in cursor.fetchall()
    }

    # -----------------------------------------------------
    # AUTO-MIGRATE OLD DATABASE
    # -----------------------------------------------------

    if "panel_message_id" not in columns:

        print(
            "⚠️ Old database detected."
        )

        print(
            "🔧 Adding panel_message_id column..."
        )

        cursor.execute("""
            ALTER TABLE farms
            ADD COLUMN panel_message_id INTEGER
        """)

        print(
            "✅ Database upgraded successfully."
        )

    # -----------------------------------------------------
    # ADD TACKLE WORLDS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # ADD SCIENCE WORLDS
    # -----------------------------------------------------

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

    db.commit()
    db.close()

    print("✅ Database initialized.")


def get_farm(world):

    db = get_db()
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

    db = get_db()
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


# =========================================================
# DISCORD BOT
# =========================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# Prevent two people from starting
# the same world simultaneously
farm_lock = asyncio.Lock()


# =========================================================
# PERMISSIONS
# =========================================================

def is_owner(user_id):
    return user_id in OWNER_USER_IDS


def is_allowed_channel(channel):

    if channel is None:
        return False

    if channel.id != CHANNEL_ID:
        return False

    if channel.category_id != ALLOWED_CATEGORY_ID:
        return False

    return True


# =========================================================
# TIME FORMAT
# =========================================================

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


# =========================================================
# FARM INFORMATION
# =========================================================

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


# =========================================================
# GET FARM CHANNEL
# =========================================================

async def get_farm_channel():

    channel = bot.get_channel(CHANNEL_ID)

    if channel is not None:
        return channel

    try:

        return await bot.fetch_channel(CHANNEL_ID)

    except Exception as e:

        print(
            f"❌ Could not find farm channel: {e}"
        )

        return None


# =========================================================
# STATUS HELPER
# =========================================================

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

    return f"⏳ `{format_time(remaining)}`"


# =========================================================
# TACKLE EMBED
# =========================================================

def tackle_embed():

    embed = discord.Embed(
        title="🎯 TACKLE FARM",
        color=discord.Color.green()
    )

    description = (
        "Harvest the world, then click its "
        "**FINISH** button.\n\n"
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


# =========================================================
# SCIENCE EMBED
# =========================================================

def science_embed():

    embed = discord.Embed(
        title="🔬 SCIENCE STATION",
        color=discord.Color.blue()
    )

    description = (
        "Harvest the world, then click its "
        "**FINISH** button.\n\n"
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


# =========================================================
# TACKLE VIEW
# =========================================================

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
                emoji="🎯",
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


# =========================================================
# SCIENCE VIEW
# =========================================================

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
                emoji="🔬",
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


# =========================================================
# GET READY BUTTONS
# =========================================================

def get_ready_tackle_worlds():

    ready_worlds = []

    for world in TACKLE_WORLDS:

        farm = get_farm(world)

        if farm["ready"]:
            ready_worlds.append(world)

        elif (
            farm["end_time"] is not None
            and farm["end_time"] <= time.time()
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
            and farm["end_time"] <= time.time()
        ):
            ready_worlds.append(world)

    return ready_worlds


# =========================================================
# FINISH WORLD
# =========================================================

async def finish_world(
    interaction,
    world
):

    # -----------------------------------------------------
    # CHANNEL CHECK
    # -----------------------------------------------------

    if not is_allowed_channel(
        interaction.channel
    ):

        await interaction.response.send_message(
            "❌ This button cannot be used here.",
            ephemeral=True
        )

        return

    # -----------------------------------------------------
    # ACKNOWLEDGE IMMEDIATELY
    # -----------------------------------------------------

    await interaction.response.defer(
        ephemeral=True
    )

    # -----------------------------------------------------
    # LOCK
    # -----------------------------------------------------

    async with farm_lock:

        farm = get_farm(world)

        # -------------------------------------------------
        # ALREADY RUNNING
        # -------------------------------------------------

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

        # -------------------------------------------------
        # START TIMER
        # -------------------------------------------------

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

    # -----------------------------------------------------
    # UPDATE PANELS
    # -----------------------------------------------------

    await update_panels()

    # -----------------------------------------------------
    # CONFIRM
    # -----------------------------------------------------

    await interaction.followup.send(
        f"✅ **{world}** timer started!\n"
        f"⏳ Next harvest in "
        f"**{format_time(timer)}**.",
        ephemeral=True
    )


# =========================================================
# UPDATE TACKLE PANEL
# =========================================================

async def update_tackle_panel():

    channel = await get_farm_channel()

    if channel is None:
        return

    if not is_allowed_channel(channel):

        print(
            "❌ Farm channel/category does not match."
        )

        return

    # -----------------------------------------------------
    # FIND EXISTING MESSAGE
    # -----------------------------------------------------

    message_id = None

    for world in TACKLE_WORLDS:

        farm = get_farm(world)

        if farm["panel_message_id"]:

            message_id = farm["panel_message_id"]

            break

    message = None

    # -----------------------------------------------------
    # FETCH MESSAGE
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # READY BUTTONS ONLY
    # -----------------------------------------------------

    ready_worlds = get_ready_tackle_worlds()

    if ready_worlds:

        view = TackleView(
            ready_worlds
        )

    else:

        view = None

    # -----------------------------------------------------
    # CREATE PANEL
    # -----------------------------------------------------

    if message is None:

        message = await channel.send(
            embed=tackle_embed(),
            view=view
        )

        # Store message ID for all tackle worlds
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

    # -----------------------------------------------------
    # UPDATE PANEL
    # -----------------------------------------------------

    await message.edit(
        embed=tackle_embed(),
        view=view
    )


# =========================================================
# UPDATE SCIENCE PANEL
# =========================================================

async def update_science_panel():

    channel = await get_farm_channel()

    if channel is None:
        return

    if not is_allowed_channel(channel):

        print(
            "❌ Farm channel/category does not match."
        )

        return

    # -----------------------------------------------------
    # FIND EXISTING MESSAGE
    # -----------------------------------------------------

    message_id = None

    for world in SCIENCE_WORLDS:

        farm = get_farm(world)

        if farm["panel_message_id"]:

            message_id = farm["panel_message_id"]

            break

    message = None

    # -----------------------------------------------------
    # FETCH MESSAGE
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # READY BUTTONS ONLY
    # -----------------------------------------------------

    ready_worlds = get_ready_science_worlds()

    if ready_worlds:

        view = ScienceView(
            ready_worlds
        )

    else:

        view = None

    # -----------------------------------------------------
    # CREATE PANEL
    # -----------------------------------------------------

    if message is None:

        message = await channel.send(
            embed=science_embed(),
            view=view
        )

        # Store message ID for all science worlds
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

    # -----------------------------------------------------
    # UPDATE PANEL
    # -----------------------------------------------------

    await message.edit(
        embed=science_embed(),
        view=view
    )


# =========================================================
# UPDATE BOTH PANELS
# =========================================================

async def update_panels():

    await update_tackle_panel()

    await update_science_panel()


# =========================================================
# SEND HARVEST PING
# =========================================================

async def send_harvest_ping(
    channel,
    world
):

    if world in TACKLE_WORLDS:

        role_ids = TACKLE_ROLE_IDS
        emoji = "🎯"
        farm_name = "Tackle Farm"

    else:

        role_ids = SCIENCE_ROLE_IDS
        emoji = "🔬"
        farm_name = "Science Station"

    mentions = []

    # -----------------------------------------------------
    # GET ROLES
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # SEND PING
    # -----------------------------------------------------

    if mentions:

        await channel.send(
            f"{' '.join(mentions)}\n\n"
            f"{emoji} **{farm_name} is ready!**\n"
            f"🌎 World: **{world}**\n"
            f"🟢 **READY TO HARVEST!**",
            allowed_mentions=discord.AllowedMentions(
                roles=True
            )
        )

    else:

        await channel.send(
            f"{emoji} **{farm_name} is ready!**\n"
            f"🌎 World: **{world}**\n"
            f"🟢 **READY TO HARVEST!**"
        )


# =========================================================
# CHECK EXPIRED TIMERS
# =========================================================

async def check_expired_timers():

    channel = await get_farm_channel()

    if channel is None:
        return

    expired_worlds = []

    async with farm_lock:

        current_time = time.time()

        for world in ALL_WORLDS:

            farm = get_farm(world)

            if farm["ready"]:
                continue

            if farm["end_time"] is None:
                continue

            # Still running
            if current_time < farm["end_time"]:
                continue

            # ------------------------------------------------
            # TIMER FINISHED
            # ------------------------------------------------

            update_farm(
                world,
                ready=True,
                end_time=None
            )

            expired_worlds.append(world)

    # -----------------------------------------------------
    # SEND PINGS OUTSIDE LOCK
    # -----------------------------------------------------

    for world in expired_worlds:

        await send_harvest_ping(
            channel,
            world
        )

    # -----------------------------------------------------
    # UPDATE PANELS
    # -----------------------------------------------------

    if expired_worlds:

        await update_panels()


# =========================================================
# TIMER LOOP
# =========================================================

@tasks.loop(seconds=10)
async def timer_loop():

    try:

        # Check finished timers
        await check_expired_timers()

        # Update countdown every 10 seconds
        await update_panels()

    except Exception as e:

        print(
            f"❌ Timer loop error: {e}"
        )


@timer_loop.before_loop
async def before_timer_loop():

    await bot.wait_until_ready()


# =========================================================
# SETUP COMMAND
# =========================================================

@bot.command()
async def setup(ctx):

    # -----------------------------------------------------
    # OWNER ONLY
    # -----------------------------------------------------

    if not is_owner(
        ctx.author.id
    ):

        await ctx.send(
            "❌ **You don't have permission "
            "to use this command.**"
        )

        return

    # -----------------------------------------------------
    # CHANNEL CHECK
    # -----------------------------------------------------

    if not is_allowed_channel(
        ctx.channel
    ):

        await ctx.send(
            "❌ This command can only be "
            "used in the configured farm channel."
        )

        return

    # -----------------------------------------------------
    # RESET ALL WORLDS
    # -----------------------------------------------------

    async with farm_lock:

        for world in ALL_WORLDS:

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


# =========================================================
# STATUS COMMAND
# =========================================================

@bot.command()
async def status(ctx):

    # -----------------------------------------------------
    # OWNER ONLY
    # -----------------------------------------------------

    if not is_owner(
        ctx.author.id
    ):

        await ctx.send(
            "❌ **You don't have permission "
            "to use this command.**"
        )

        return

    # -----------------------------------------------------
    # CHANNEL CHECK
    # -----------------------------------------------------

    if not is_allowed_channel(
        ctx.channel
    ):

        await ctx.send(
            "❌ This command can only be "
            "used in the configured farm channel."
        )

        return

    # -----------------------------------------------------
    # EMBED
    # -----------------------------------------------------

    embed = discord.Embed(
        title="🌾 Farm Status",
        color=discord.Color.blurple()
    )

    # =====================================================
    # TACKLE
    # =====================================================

    tackle_text = ""

    for world in TACKLE_WORLDS:

        tackle_text += (
            f"🎯 `{world}` → "
            f"{get_world_status(world)}\n"
        )

    embed.add_field(
        name="🎯 Tackle — 48 Hours",
        value=tackle_text,
        inline=False
    )

    # =====================================================
    # SCIENCE
    # =====================================================

    science_text = ""

    for world in SCIENCE_WORLDS:

        science_text += (
            f"🔬 `{world}` → "
            f"{get_world_status(world)}\n"
        )

    embed.add_field(
        name="🔬 Science Station — 12 Hours",
        value=science_text,
        inline=False
    )

    await ctx.send(
        embed=embed
    )


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    print(
        "-----------------------------------"
    )

    print(
        f"✅ Logged in as {bot.user}"
    )

    print(
        f"🆔 Bot ID: {bot.user.id}"
    )

    print(
        "-----------------------------------"
    )

    # -----------------------------------------------------
    # DATABASE
    # -----------------------------------------------------

    initialize_database()

    # -----------------------------------------------------
    # REGISTER PERSISTENT VIEWS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # CHECK EXPIRED TIMERS
    # -----------------------------------------------------

    await check_expired_timers()

    # -----------------------------------------------------
    # CREATE/UPDATE ONLY TWO PANELS
    # -----------------------------------------------------

    await update_panels()

    # -----------------------------------------------------
    # START TIMER LOOP
    # -----------------------------------------------------

    if not timer_loop.is_running():

        timer_loop.start()

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
        "-----------------------------------"
    )


# =========================================================
# ERROR HANDLER
# =========================================================

@bot.event
async def on_command_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.CommandNotFound
    ):

        return

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        await ctx.send(
            "❌ You are missing "
            "a required argument."
        )

        return

    print(
        f"Command error: {error}"
    )
# =========================
# RUN
# =========================
if __name__ == "__main__":
    keep_alive()
    bot.run(os.getenv("TOKEN"))
