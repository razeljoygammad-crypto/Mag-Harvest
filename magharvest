import discord
from discord.ext import commands, tasks
from discord import app_commands

from flask import Flask
import os
from threading import Thread
import time
import json

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
# Users allowed to use !setup and !status
# Add/remove IDs as needed.
OWNER_USER_IDS = {
    923096413934616596,
    760023911764197396,
}

# Only this category is allowed to use the farm system
ALLOWED_CATEGORY_ID = 1401449789983428719

# Farm channel
CHANNEL_ID = 1401449829095182437

# Roles to ping
SCIENCE_ROLE_USER_IDS = {
    1401454637877297253,
    1401455558514577489,

}

TACKLE_ROLE_USER_IDS = {
    1401454637877297253,
    1401455558514577489,

}

# =========================================================
# FARM TIMER SETTINGS
# =========================================================

SCIENCE_TIME = 10 * 60 * 60       # 10 hours
TACKLE_TIME = 48 * 60 * 60        # 48 hours

TIMER_FILE = "timers.json"

# =========================================================
# DISCORD BOT SETUP
# =========================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# Prevent registering persistent views multiple times
views_registered = False

# =========================================================
# FARM DATA
# =========================================================

science = {
    "ready": True,
    "end_time": None,
    "message_id": None
}

tackle = {
    "ready": True,
    "end_time": None,
    "message_id": None
}


# =========================================================
# SAVE / LOAD TIMER DATA
# =========================================================

def save_timers():
    data = {
        "science": science,
        "tackle": tackle
    }

    with open(TIMER_FILE, "w") as f:
        json.dump(data, f, indent=4)


def load_timers():
    global science, tackle

    if not os.path.exists(TIMER_FILE):
        save_timers()
        return

    try:
        with open(TIMER_FILE, "r") as f:
            data = json.load(f)

        if "science" in data:
            science.update(data["science"])

        if "tackle" in data:
            tackle.update(data["tackle"])

    except Exception as e:
        print(f"❌ Failed to load timers.json: {e}")


# =========================================================
# PERMISSION CHECKS
# =========================================================

def is_owner(user_id: int):
    """
    Only these users can use owner commands.
    Buttons are NOT restricted by this.
    """
    return user_id in OWNER_USER_IDS


def is_allowed_channel(channel):
    """
    Makes sure the command/button is being used
    inside the configured category and channel.
    """

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
    seconds = max(0, int(seconds))

    days = seconds // 86400
    seconds %= 86400

    hours = seconds // 3600
    seconds %= 3600

    minutes = seconds // 60
    seconds %= 60

    if days > 0:
        return f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"

    return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"


# =========================================================
# EMBEDS
# =========================================================

def science_embed():
    embed = discord.Embed(
        title="🔬 Science Farm",
        color=discord.Color.blue()
    )

    if science["ready"]:
        embed.description = (
            "🟢 **READY TO HARVEST!**\n\n"
            "Click **FINISH** after harvesting."
        )

    else:
        remaining = science["end_time"] - time.time()

        if remaining <= 0:
            embed.description = "🟢 **READY TO HARVEST!**"
        else:
            embed.description = (
                f"⏳ **Next harvest:** `{format_time(remaining)}`"
            )

    return embed


def tackle_embed():
    embed = discord.Embed(
        title="🎯 Tackle Farm",
        color=discord.Color.green()
    )

    if tackle["ready"]:
        embed.description = (
            "🟢 **READY TO HARVEST!**\n\n"
            "Click **FINISH** after harvesting."
        )

    else:
        remaining = tackle["end_time"] - time.time()

        if remaining <= 0:
            embed.description = "🟢 **READY TO HARVEST!**"
        else:
            embed.description = (
                f"⏳ **Next harvest:** `{format_time(remaining)}`"
            )

    return embed


# =========================================================
# VIEWS / BUTTONS
# =========================================================

class ScienceView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="FINISH",
        style=discord.ButtonStyle.green,
        emoji="🔬",
        custom_id="science_finish_button"
    )
    async def finish(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        # Anyone can click the button.
        # We only restrict the channel/category.
        if not is_allowed_channel(interaction.channel):
            await interaction.response.send_message(
                "❌ This button cannot be used here.",
                ephemeral=True
            )
            return

        # Already running
        if not science["ready"]:
            remaining = science["end_time"] - time.time()

            if remaining > 0:
                await interaction.response.send_message(
                    f"⏳ Science is already running.\n"
                    f"Next harvest: **{format_time(remaining)}**",
                    ephemeral=True
                )
                return

        # Start timer
        science["ready"] = False
        science["end_time"] = time.time() + SCIENCE_TIME

        save_timers()

        await interaction.response.defer()

        await update_science_message()


class TackleView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="FINISH",
        style=discord.ButtonStyle.green,
        emoji="🎯",
        custom_id="tackle_finish_button"
    )
    async def finish(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        # Anyone can click the button.
        if not is_allowed_channel(interaction.channel):
            await interaction.response.send_message(
                "❌ This button cannot be used here.",
                ephemeral=True
            )
            return

        # Already running
        if not tackle["ready"]:
            remaining = tackle["end_time"] - time.time()

            if remaining > 0:
                await interaction.response.send_message(
                    f"⏳ Tackle is already running.\n"
                    f"Next harvest: **{format_time(remaining)}**",
                    ephemeral=True
                )
                return

        # Start timer
        tackle["ready"] = False
        tackle["end_time"] = time.time() + TACKLE_TIME

        save_timers()

        await interaction.response.defer()

        await update_tackle_message()


# =========================================================
# GET FARM CHANNEL
# =========================================================

async def get_farm_channel():
    channel = bot.get_channel(CHANNEL_ID)

    if channel is not None:
        return channel

    try:
        channel = await bot.fetch_channel(CHANNEL_ID)
        return channel

    except Exception as e:
        print(f"❌ Could not find farm channel: {e}")
        return None


# =========================================================
# UPDATE SCIENCE MESSAGE
# =========================================================

async def update_science_message():
    channel = await get_farm_channel()

    if channel is None:
        return

    if not is_allowed_channel(channel):
        print("❌ CHANNEL_ID is not inside ALLOWED_CATEGORY_ID.")
        return

    message = None

    # Try existing message
    if science["message_id"]:
        try:
            message = await channel.fetch_message(
                science["message_id"]
            )
        except discord.NotFound:
            message = None
        except Exception as e:
            print(f"❌ Science message error: {e}")

    # If message doesn't exist, create it
    if message is None:

        if science["ready"]:
            view = ScienceView()
        else:
            view = None

        message = await channel.send(
            embed=science_embed(),
            view=view
        )

        science["message_id"] = message.id
        save_timers()

        return

    # Timer running
    if not science["ready"]:
        remaining = science["end_time"] - time.time()

        if remaining > 0:
            await message.edit(
                embed=science_embed(),
                view=None
            )
            return

    # Ready
    await message.edit(
        embed=science_embed(),
        view=ScienceView()
    )


# =========================================================
# UPDATE TACKLE MESSAGE
# =========================================================

async def update_tackle_message():
    channel = await get_farm_channel()

    if channel is None:
        return

    if not is_allowed_channel(channel):
        print("❌ CHANNEL_ID is not inside ALLOWED_CATEGORY_ID.")
        return

    message = None

    # Try existing message
    if tackle["message_id"]:
        try:
            message = await channel.fetch_message(
                tackle["message_id"]
            )
        except discord.NotFound:
            message = None
        except Exception as e:
            print(f"❌ Tackle message error: {e}")

    # If message doesn't exist, create it
    if message is None:

        if tackle["ready"]:
            view = TackleView()
        else:
            view = None

        message = await channel.send(
            embed=tackle_embed(),
            view=view
        )

        tackle["message_id"] = message.id
        save_timers()

        return

    # Timer running
    if not tackle["ready"]:
        remaining = tackle["end_time"] - time.time()

        if remaining > 0:
            await message.edit(
                embed=tackle_embed(),
                view=None
            )
            return

    # Ready
    await message.edit(
        embed=tackle_embed(),
        view=TackleView()
    )


# =========================================================
# EXPIRED TIMER CHECK
# =========================================================

async def check_expired_timers():
    channel = await get_farm_channel()

    if channel is None:
        return

    # -----------------------------------------------------
    # SCIENCE
    # -----------------------------------------------------

    if not science["ready"] and science["end_time"] is not None:

        if time.time() >= science["end_time"]:

            science["ready"] = True
            science["end_time"] = None

            save_timers()

            role = channel.guild.get_role(SCIENCE_ROLE_ID)

            if role:
                await channel.send(
                    f"{role.mention} 🔬 **Science Farm is ready to harvest!**",
                    allowed_mentions=discord.AllowedMentions(
                        roles=True
                    )
                )
            else:
                print(
                    f"❌ Science role {SCIENCE_ROLE_ID} not found."
                )

            await update_science_message()

    # -----------------------------------------------------
    # TACKLE
    # -----------------------------------------------------

    if not tackle["ready"] and tackle["end_time"] is not None:

        if time.time() >= tackle["end_time"]:

            tackle["ready"] = True
            tackle["end_time"] = None

            save_timers()

            role = channel.guild.get_role(TACKLE_ROLE_ID)

            if role:
                await channel.send(
                    f"{role.mention} 🎯 **Tackle Farm is ready to harvest!**",
                    allowed_mentions=discord.AllowedMentions(
                        roles=True
                    )
                )
            else:
                print(
                    f"❌ Tackle role {TACKLE_ROLE_ID} not found."
                )

            await update_tackle_message()


# =========================================================
# TIMER LOOP
# =========================================================

@tasks.loop(seconds=10)
async def timer_loop():

    await check_expired_timers()

    # Update countdown only if currently running
    if not science["ready"]:
        await update_science_message()

    if not tackle["ready"]:
        await update_tackle_message()


@timer_loop.before_loop
async def before_timer_loop():
    await bot.wait_until_ready()


# =========================================================
# SETUP COMMAND
# =========================================================

@bot.command()
async def setup(ctx):

    # ONLY YOU CAN USE THIS
    if not is_owner(ctx.author.id):
        await ctx.send(
            "❌ **You don't have permission to use this command.**"
        )
        return

    # Must be in correct channel/category
    if not is_allowed_channel(ctx.channel):
        await ctx.send(
            "❌ This command can only be used in the configured farm channel."
        )
        return

    # Reset Science
    science["ready"] = True
    science["end_time"] = None
    science["message_id"] = None

    # Reset Tackle
    tackle["ready"] = True
    tackle["end_time"] = None
    tackle["message_id"] = None

    save_timers()

    # Create fresh messages
    science_message = await ctx.channel.send(
        embed=science_embed(),
        view=ScienceView()
    )

    science["message_id"] = science_message.id

    tackle_message = await ctx.channel.send(
        embed=tackle_embed(),
        view=TackleView()
    )

    tackle["message_id"] = tackle_message.id

    save_timers()

    await ctx.send(
        "✅ **Farm system has been reset!**\n\n"
        "🔬 Science → READY \n"
        "World Name: {world_name}\n"
        "🎯 Tackle → READY \n"
        "World Name: {EVDYT}\n\n"
        "Please Click the FINISH button if done."
    )


# =========================================================
# STATUS COMMAND
# =========================================================

@bot.command()
async def status(ctx):

    # ONLY YOU CAN USE THIS
    if not is_owner(ctx.author.id):
        await ctx.send(
            "❌ **You don't have permission to use this command.**"
        )
        return

    # Correct channel/category
    if not is_allowed_channel(ctx.channel):
        await ctx.send(
            "❌ This command can only be used in the configured farm channel."
        )
        return

    embed = discord.Embed(
        title="🌾 Farm Status",
        color=discord.Color.blurple()
    )

    # Science status
    if science["ready"]:
        science_status = "🟢 **READY**"
    else:
        remaining = science["end_time"] - time.time()

        if remaining <= 0:
            science_status = "🟢 **READY**"
        else:
            science_status = (
                f"⏳ **{format_time(remaining)} remaining**"
            )

    # Tackle status
    if tackle["ready"]:
        tackle_status = "🟢 **READY**"
    else:
        remaining = tackle["end_time"] - time.time()

        if remaining <= 0:
            tackle_status = "🟢 **READY**"
        else:
            tackle_status = (
                f"⏳ **{format_time(remaining)} remaining**"
            )

    embed.add_field(
        name="🔬 Science",
        value=science_status,
        inline=False
    )

    embed.add_field(
        name="🎯 Tackle",
        value=tackle_status,
        inline=False
    )

    await ctx.send(embed=embed)


# =========================================================
# READY EVENT
# =========================================================

@bot.event
async def on_ready():

    global views_registered

    print("-----------------------------------")
    print(f"✅ Logged in as {bot.user}")
    print(f"🆔 Bot ID: {bot.user.id}")
    print("-----------------------------------")

    load_timers()

    # Register persistent buttons
    if not views_registered:
        bot.add_view(ScienceView())
        bot.add_view(TackleView())
        views_registered = True

    # Check timers that may have expired while bot was offline
    await check_expired_timers()

    # Make sure farm messages exist
    await update_science_message()
    await update_tackle_message()

    # Start timer loop
    if not timer_loop.is_running():
        timer_loop.start()

    print("🌾 Farm timer system is running!")


# =========================================================
# ERROR HANDLER
# =========================================================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "❌ You are missing a required argument."
        )
        return

    print(f"Command error: {error}")


# =========================
# RUN
# =========================
if __name__ == "__main__":
    keep_alive()
    bot.run(os.getenv("TOKEN"))
