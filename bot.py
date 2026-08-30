import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from discord.errors import Forbidden
from database.db import (setup_database, get_character_configs, get_guild_settings, get_verification_log_channel, get_admin_log_channel, get_character_role_requirements, get_custom_roles)
from PIL import Image, ImageOps
import io
from PIL import ImageDraw
from PIL import ImageFilter
import numpy as np
import pytesseract
import easyocr
import re
import datetime
from enka_fetcher import get_character_status
from utils.character_cache import (update_hsr_cache)
import os
from dotenv import load_dotenv
pytesseract.pytesseract.tesseract_cmd = r"D:\Tesseract\tesseract.exe"


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
load_dotenv()
OWNER_ID = int(os.getenv("OWNER_ID"))
GUILD_ID = int(os.getenv("TEST_GUILD_ID"))

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    owner_id=OWNER_ID,
    allowed_mentions=discord.AllowedMentions(
        roles=False)
)

# =========================
# DEBUG SETTINGS
# =========================
EIDOLON_DEBUG = True
SKIP_OWNER_CHECK = True

# =========================
# Region of Interests Config
# =========================

# TUPLE Image (left, top, right, bottom)


ROI_DEFS = {
    "tablet": {
        "uid": {
            "x1": 0.018, "y1": 0.959,
            "x2": 0.112, "y2": 0.996
        },
        "obtained_date": {
            "x1": 0.871, "y1": 0.300,
            "x2": 0.986, "y2": 0.355
        },
        "name": {
            "x1": 0.755,    "y1": 0.050,
            "x2": 0.930,    "y2": 0.125

        }
    },

        "mobile": {
        "uid": {
            "x1": 0.040, "y1": 0.955,
            "x2": 0.132, "y2": 0.985
        },
        "obtained_date": {
            "x1": 0.850, "y1": 0.315,
            "x2": 0.965, "y2": 0.385
        },
        "name": {
            "x1": 0.730,    "y1": 0.045,
            "x2": 0.935,    "y2": 0.125
        }
    },

    "pc": {
        "uid": {
            "x1": 0.012,    "y1": 0.962,
            "x2": 0.089,    "y2": 0.996
        },
        "obtained_date": {
            "x1": 0.890,    "y1": 0.274,
            "x2": 0.990,    "y2": 0.324
        },
        "name":{
            "x1": 0.765,    "y1": 0.050,
            "x2": 0.935,    "y2": 0.125
        } 
    }
}

# =========================
# EIDOLON CONFIG  (Creates a Box from that point)
# =========================

EIDOLON_ROIS = {
    "pc": [
        {"x": 0.38, "y": 0.20},  # 1
        {"x": 0.58, "y": 0.25},  # 2
        {"x": 0.80, "y": 0.38},  # 3
        {"x": 0.72, "y": 0.85},  # 4
        {"x": 0.47, "y": 0.78},  # 5
        {"x": 0.23, "y": 0.69},  # 6
    ],
    "tablet": [
        {"x": 0.50, "y": 0.22},
        {"x": 0.65, "y": 0.30},
        {"x": 0.78, "y": 0.47},
        {"x": 0.68, "y": 0.72},
        {"x": 0.48, "y": 0.80},
        {"x": 0.30, "y": 0.67},
    ],
    "mobile": [
        {"x": 0.52, "y": 0.24},
        {"x": 0.66, "y": 0.33},
        {"x": 0.78, "y": 0.49},
        {"x": 0.67, "y": 0.73},
        {"x": 0.47, "y": 0.80},
        {"x": 0.28, "y": 0.67},
    ]
}

EIDOLON_BOX_SIZE = 0.058

# =========================
# EIDOLON DETECTION TUNING
# =========================

EIDOLON_COLOR_DIFF_THRESHOLD = 30 
# detects colour difference per pixel
# 20–25 -> more sensitive (even slight colour variation counts)
# 40–50 -> stricter (only strong colours like gold/purple detected)

EIDOLON_BRIGHT_THRESHOLD = 180 
# detects pixel brightness
# 150 -> lower (more pixels counted as bright, includes soft glow)
# 200 -> higher (only very bright/glowing pixels counted)

EIDOLON_DARK_THRESHOLD = 70 
# detects how dark a pixel is
# 60 -> very strict (only very dark/black pixels)
# 100 -> more tolerant (dark gray also counted)

EIDOLON_COLOR_RATIO = 0.20 
# minimum % of pixels that must be colorful
# lower (0.15–0.20) -> easier to mark as ACTIVE
# higher (0.30+) -> stricter, requires strong colour presence

EIDOLON_BRIGHT_RATIO = 0.30 
# % of bright pixels required (currently NOT used in logic, debug only)
# lower -> glow easier to detect
# higher -> only strong glowing nodes pass

EIDOLON_DARK_RATIO = 0.30 
# % of dark pixels (currently NOT used directly, debug only)
# useful to observe lock patterns vs background darkness

EIDOLON_CENTER_CROP = 0.30 
# start of center crop (removes outer shard/background)
# higher (0.45) -> tighter crop, focuses more on icon center
# lower (0.30) -> wider crop, includes more background (risk of noise)

EIDOLON_CENTER_CROP_END = 0.70
# end of center crop
# should match CENTER_CROP range (e.g. 0.40–0.60 = middle 20%)
# smaller gap -> tighter focus on icon

EIDOLON_LOCK_DARK_THRESHOLD = 70
# brightness threshold for detecting lock icon darkness
# lower (60–70) -> only very dark lock pixels counted
# higher (90–100) -> includes gray lock areas (more reliable)

EIDOLON_LOCK_RATIO = 0.33
# % of dark pixels required to classify as LOCKED
# lower (0.20) -> easier to mark as locked
# higher (0.35+) -> stricter, reduces false locks

EIDOLON_VARIANCE_THRESHOLD = 30
# detects pixel-to-pixel color variation (detail / texture)
# lower (20–25) -> sensitive (even smooth gradients count)
# higher (40+) -> only sharp edges/details counted (better for icons)

EIDOLON_VARIANCE_RATIO = 0.22
# % of pixels that must have high variation
# lower (0.10–0.15) -> easier to mark ACTIVE
# higher (0.25+) -> stricter, requires strong icon detail

# =========================
# GLOBAL VERIFICATION STATE
# =========================

verification_enabled = False
reader = easyocr.Reader(['en'], gpu=False)
bomb_semaphore = asyncio.Semaphore(3)
VERIFY_CONCURRENCY_LIMIT = 2
verify_semaphores = {}
verify_queues = {}
verify_active_counts = {}
verify_queue_lock = asyncio.Lock()

stats = {
    "checked": 0,
    "passed": 0,
    "failed": 0
}

# =========================
# DEFAULT TAG CONFIG
# =========================

DEFAULT_TAGS = {
    "verify_tag": "Bot Test",
    "progress_tag": "In Progress",
    "approved_tag": "Approved",
    "denied_tag": "Denied",
    "failed_tag": "Bot Failed"
}


# =========================
# EVENTS
# =========================

async def setup_hook():
    try:
        print("Loading databases...")
        await setup_database()
        await update_hsr_cache()
        print("Databases loaded.")
        print("Loading extensions...")
        await bot.load_extension("jishaku")
        print("jishaku loaded.")
        await bot.load_extension("cogs.admin")
        print("cogs.admin loaded.")
        await bot.load_extension("cogs.fun")
        print("cogs.fun loaded.")
        print("Extensions loaded.")
        
        bot.loop.create_task(verification_worker())
        print("Verification worker started.")
        bot.loop.create_task(cache_worker())
        print("Cache worker started.")
    except Exception as e:
        print("Extension load failed:", e)

bot.setup_hook = setup_hook

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    # Sync slash commands
    try:
        guild = discord.Object(id=GUILD_ID)

        # bot.tree.clear_commands(guild=guild)
        # await bot.tree.sync(guild=guild)

        # bot.tree.clear_commands(guild=None)
        # await bot.tree.sync()

        # bot.tree.copy_global_to(guild=guild)
        # await bot.tree.sync(guild=guild)
        # await bot.tree.sync()
        bot.tree.copy_global_to(guild=guild)
        guild_synced = await bot.tree.sync(guild=guild)
        global_synced = await bot.tree.sync()

        print(f"Guild synced: {len(guild_synced)}")
        print(f"Global synced: {len(global_synced)}")
    except Exception as e:
        print("Slash sync failed:", e)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.lower() == "hello":
        await message.channel.send("Hello!")
        print(message.author.name)

    elif message.content.lower() == "sparxie":
        await message.channel.send("i am here! I Am There! I AM EVERYWHERE!")
        print(message.author.name)

    elif message.content.lower() == "sparkle":
        await message.channel.send("Why are you taking about that old model!")
        print(message.author.name)

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):

    # Ignore unknown commands silently
    if isinstance(error, commands.CommandNotFound):
        return

    # Jishaku / owner only
    if isinstance(error, commands.NotOwner):
        await ctx.send(
            "❌ You do not have permission to use that command.",
            delete_after=5
        )
        return

    # Missing permissions
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "❌ You are missing permissions.",
            delete_after=5
        )
        return

    # Cooldown [don't know why we need a cooldown when I won't spam but i guess it's needed? bruh]
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            f"⏳ Try again in {error.retry_after:.1f}s",
            delete_after=5
        )
        return

    # Anything else
    print("Unhandled command error:", repr(error))



# =========================
# COMMANDS
# =========================

async def verification_worker():
    await bot.wait_until_ready()

    while not bot.is_closed():
        if verification_enabled:
            for guild in bot.guilds:
                await scan_forum_posts(guild)

        await asyncio.sleep(10)  # wait before next scan

def get_verify_semaphore(guild_id):
    if guild_id not in verify_semaphores:
        verify_semaphores[guild_id] = asyncio.Semaphore(
            VERIFY_CONCURRENCY_LIMIT
        )

    return verify_semaphores[guild_id]

async def enter_verify_queue(guild_id, request_id):
    async with verify_queue_lock:
        semaphore = get_verify_semaphore(guild_id)
        queue = verify_queues.setdefault(guild_id, [])
        queue.append(request_id)

        position = len(queue)
        active_count = verify_active_counts.get(guild_id, 0)

        if position == 1 and active_count < VERIFY_CONCURRENCY_LIMIT:
            await semaphore.acquire()
            verify_active_counts[guild_id] = active_count + 1
            queue.pop(0)
            return False, 0, active_count, True

        return True, position, active_count, False

async def acquire_verify_slot(guild_id, request_id):
    while True:
        async with verify_queue_lock:
            semaphore = get_verify_semaphore(guild_id)
            queue = verify_queues.setdefault(guild_id, [])
            active_count = verify_active_counts.get(guild_id, 0)

            if (
                queue
                and queue[0] == request_id
                and active_count < VERIFY_CONCURRENCY_LIMIT
            ):
                await semaphore.acquire()
                verify_active_counts[guild_id] = active_count + 1
                queue.pop(0)
                return

        await asyncio.sleep(0.25)

async def release_verify_slot(guild_id):
    async with verify_queue_lock:
        semaphore = get_verify_semaphore(guild_id)
        active_count = verify_active_counts.get(guild_id, 0)

        if active_count <= 0:
            return

        verify_active_counts[guild_id] = active_count - 1
        semaphore.release()

async def leave_verify_queue(guild_id, request_id):
    async with verify_queue_lock:
        queue = verify_queues.get(guild_id)

        if queue and request_id in queue:
            queue.remove(request_id)

async def cache_worker():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            await update_hsr_cache()

        except Exception as e:

            print(
                f"Cache refresh failed:{e}"
            )

        await asyncio.sleep(
            36000
        )

# =========================
# Forum Scaning and Processing
# =========================

async def get_configured_tags(guild_id):
    settings = await get_guild_settings(guild_id)

    tags = DEFAULT_TAGS.copy()

    if settings:
        for key in tags:
            if settings.get(key):
                tags[key] = settings[key]

    return tags

async def scan_forum_posts(guild):
    settings = await get_guild_settings(guild.id)

    if not settings or not settings.get("forum_channel_id"):
        return

    forum = guild.get_channel(settings["forum_channel_id"])
    if forum is None:
        return

    tags = await get_configured_tags(guild.id)

    # forum.threads = active (non-archived) posts
    for thread in forum.threads:
        tag_names = [tag.name for tag in thread.applied_tags]

        if tags["verify_tag"] in tag_names:
            await process_thread(thread)

def has_signature_lc(config, lc):
    if not config or not lc:
        return False

    return (
        lc["name"]==

        config[
            "signature_lightcone_name"
        ]
    )

async def verification_log(guild, title, message):
    log_channel_id = await get_verification_log_channel(guild.id)

    if not log_channel_id:
        return

    log_channel = guild.get_channel(log_channel_id)

    if not log_channel:
        return

    await log_channel.send(
        f"**{title}**\n{message}"
    )

async def admin_log(guild, title, message):
    log_channel_id = await get_admin_log_channel(guild.id)

    if not log_channel_id:
        return

    log_channel = guild.get_channel(log_channel_id)

    if not log_channel:
        return

    await log_channel.send(
        f"**{title}**\n{message}"
    )

def parse_date_text(text):
    match = re.search(
        r"(\d{4})\D{1,3}(\d{1,2})\D{1,3}(\d{1,2})",
        text
    )

    if not match:
        return None

    year, month, day = match.groups()

    try:
        return datetime.date(
            int(year),
            int(month),
            int(day)
        )
    except ValueError:
        return None

def extract_obtained_date_from_image(date_img, thread_id=None):
    print(">>> ENTERED extract_obtained_date_from_image")
    scale = 5

    gray = date_img.convert("L")
    gray = gray.resize(
        (gray.width * scale, gray.height * scale),
        Image.Resampling.LANCZOS
    )
    gray = gray.filter(
        ImageFilter.UnsharpMask(radius=1, percent=80)
    )
    print("Running Tesseract...")
    if thread_id:
        gray.save(f"debug_obtained_date_{thread_id}.png")

    text = pytesseract.image_to_string(
        gray,
        config="--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789/-.: Obtainedobtained"
    )

    print("Obtained Date OCR Raw:", repr(text))

    print("Tesseract finished")
    parsed = parse_date_text(text)

    if parsed:
        return parsed, text.strip()

    print("Running EasyOCR...")
    results = reader.readtext(
        np.array(date_img),
        detail=0,
        paragraph=False
    )

    easy_text = " ".join(results)
    print("Obtained Date EasyOCR Raw:", repr(easy_text))

    return parse_date_text(easy_text), easy_text

def uid_sliding_windows(digit_string):
    if len(digit_string) < 9:
        return []

    return [
        digit_string[i:i + 9]
        for i in range(len(digit_string) - 8)
    ]

def build_uid_candidate(method, raw_text):
    digits = re.sub(r"\D", "", raw_text)

    if len(digits) == 9:
        status = "direct"
    elif len(digits) > 9:
        status = "repair"
    else:
        status = "invalid"

    return {
        "method": method,
        "raw_text": raw_text.strip(),
        "digits": digits,
        "status": status
    }

def find_matching_uid_candidate(expected_uid, debug_data):
    for candidate in debug_data.get("candidates", []):
        if candidate["status"] == "invalid":
            continue

        if candidate["status"] == "direct":
            if candidate["digits"] == expected_uid:
                return expected_uid

        if candidate["status"] == "repair":
            windows = uid_sliding_windows(
                candidate["digits"]
            )

            if expected_uid in windows:
                return expected_uid

    return None

def format_uid_ocr_debug(debug_data):
    lines = ["OCR Attempts"]

    for candidate in debug_data.get("candidates", []):
        lines.append("")
        lines.append(
            f"{candidate['method']} -> {candidate['status']}"
        )

        if candidate["digits"]:
            lines.append(candidate["digits"])

    votes = debug_data.get("votes", {})

    lines.append("")

    if votes:
        lines.append("Votes")

        for uid, count in votes.items():
            lines.append("")
            lines.append(f"{uid} -> {count}")
    else:
        lines.append("No valid 9-digit candidates.")

    lines.append("")
    lines.append("Winner")
    lines.append(str(debug_data.get("winner")))

    return "\n".join(lines)

def easyocr_uid(img):
    results = reader.readtext(
        np.array(img),
        detail=0,
        paragraph=False
    )

    text = " ".join(results)
    print("EasyOCR Raw:", repr(text))

    return build_uid_candidate(
        "EasyOCR",
        text
    )

def extract_uid_from_image(uid_img, thread_id=None):
    scale = 8

    # =========================
    # Helper OCR Function
    # =========================
    def run_ocr(img, label):
        text = pytesseract.image_to_string(
            img,
            config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789UID:"
        )

        print(f"OCR Raw ({label}):", repr(text))

        return build_uid_candidate(
            label,
            text
        )

    def print_uid_debug(debug_data):
        print("========== UID OCR ==========")

        for candidate in debug_data["candidates"]:
            print(candidate["method"])

            if candidate["digits"]:
                print(f"digits: {candidate['digits']}")
            else:
                print("digits: None")

            print(f"status: {candidate['status']}")
            print()

        if debug_data["votes"]:
            print("Votes")

            for uid, count in debug_data["votes"].items():
                print(f"{uid} -> {count}")

            print()
            print("Winner")
            print(debug_data["winner"])
        else:
            print("No valid 9-digit candidates.")

        print("=============================")

    candidates = []

    # =========================
    # Attempt 1: Black / White
    # =========================
    gray = uid_img.convert("L")

    gray = gray.resize(
        (gray.width * scale, gray.height * scale),
        Image.Resampling.LANCZOS
    )
    gray = gray.filter(
    ImageFilter.UnsharpMask(radius=1, percent=70)
    )

    # =========================
    # Multi Threshold BW OCR
    # =========================
    thresholds = [110, 125, 140, 160]

    for t in thresholds:
        bw = gray.point(lambda x: 255 if x > t else 0)

        if thread_id:
            bw.save(f"debug_uid_bw_{t}_{thread_id}.png")

        candidates.append(
            run_ocr(bw, f"BW{t}")
        )

    # =========================
    # Attempt 2: Grayscale
    # =========================
    gray2 = uid_img.convert("L")

    gray2 = gray2.resize(
        (gray2.width * scale, gray2.height * scale),
        Image.Resampling.LANCZOS
    )

    if thread_id:
        gray2.save(f"debug_uid_gray_{thread_id}.png")

    candidates.append(
        run_ocr(gray2, "GRAY")
    )

    # =========================
    # Attempt 3: Full Color
    # =========================
    color = uid_img.resize(
        (uid_img.width * scale, uid_img.height * scale),
        Image.Resampling.LANCZOS
    )

    if thread_id:
        color.save(f"debug_uid_color_{thread_id}.png")

    candidates.append(
        run_ocr(color, "COLOR")
    )

    # =========================
    # EasyOCR Fallback
    # =========================
    print("Trying EasyOCR fallback...")

    # Save debug image
    if thread_id:
        color.save(f"debug_uid_easyocr_{thread_id}.png")

    candidates.append(
        easyocr_uid(color)
    )

    votes = {}
    first_seen = {}

    for index, candidate in enumerate(candidates):
        if candidate["status"] != "direct":
            continue

        uid = candidate["digits"]
        votes[uid] = votes.get(uid, 0) + 1

        if uid not in first_seen:
            first_seen[uid] = index

    winner = None

    if votes:
        winner = sorted(
            votes,
            key=lambda uid: (-votes[uid], first_seen[uid])
        )[0]

    debug_data = {
        "winner": winner,
        "candidates": candidates,
        "votes": votes
    }

    print_uid_debug(debug_data)

    if winner:
        return winner, debug_data

    # =========================
    # All Failed
    # =========================
    print("OCR Failed In All Modes")

    return None, debug_data

def extract_name_from_image(name_img, thread_id=None):
    scale = 5

    # =========================
    # Prepare enlarged original color ROI once
    # =========================
    color = name_img.resize(
        (name_img.width * scale, name_img.height * scale),
        Image.Resampling.LANCZOS
    )

    gray = color.convert("L")

    gray = gray.filter(
        ImageFilter.UnsharpMask(
            radius=1,
            percent=80
        )
    )

    if thread_id:
        color.save(f"debug_name_color_{thread_id}.png")
        gray.save(f"debug_name_{thread_id}.png")

    config = (
        "--oem 3 "
        "--psm 7 "
        "-c tessedit_char_whitelist="
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789"
        " .-'"
    )

    def build_name_candidate(method, raw_text):
        raw = raw_text.strip()
        normalized = normalize_name(raw) if raw else ""

        return {
            "method": method,
            "raw": raw,
            "normalized": normalized
        }

    def run_tesseract(img, label):
        text = pytesseract.image_to_string(
            img,
            config=config
        )

        print(f"Character Name OCR Raw ({label}):", repr(text))

        return build_name_candidate(
            label,
            text
        )

    candidates = []

    # =========================
    # Multi Threshold BW OCR
    # =========================
    thresholds = [110, 125, 140, 160]

    for t in thresholds:
        bw = gray.point(lambda x: 255 if x > t else 0)

        if thread_id:
            bw.save(f"debug_name_bw_{t}_{thread_id}.png")

        candidates.append(
            run_tesseract(bw, f"BW{t}")
        )

    # =========================
    # Grayscale and Color Tesseract
    # =========================
    candidates.append(
        run_tesseract(gray, "GRAY")
    )

    candidates.append(
        run_tesseract(color, "COLOR")
    )

    # =========================
    # EasyOCR on enlarged original color ROI
    # =========================
    print("Trying EasyOCR for character name...")

    results = reader.readtext(
        np.array(color),
        detail=0,
        paragraph=False
    )

    easy_text = " ".join(results).strip()

    print("Character Name EasyOCR Raw:", repr(easy_text))

    candidates.append(
        build_name_candidate(
            "EasyOCR",
            easy_text
        )
    )

    votes = {}
    first_seen = {}
    raw_by_name = {}
    method_by_name = {}

    for index, candidate in enumerate(candidates):
        normalized = candidate["normalized"]

        if not normalized:
            continue

        votes[normalized] = votes.get(normalized, 0) + 1

        if normalized not in first_seen:
            first_seen[normalized] = index
            raw_by_name[normalized] = candidate["raw"]
            method_by_name[normalized] = candidate["method"]

    print("========== Character Name OCR ==========")

    for candidate in candidates:
        print(
            f"{candidate['method']}: "
            f"{repr(candidate['raw'])} -> "
            f"{candidate['normalized'] or 'None'}"
        )

    winner = None

    if votes:
        max_votes = max(votes.values())
        tied = [
            name
            for name, count in votes.items()
            if count == max_votes
        ]
        easy_candidate = next(
            (
                candidate["normalized"]
                for candidate in candidates
                if (
                    candidate["method"] == "EasyOCR"
                    and candidate["normalized"] in tied
                )
            ),
            None
        )

        winner = easy_candidate or sorted(
            tied,
            key=lambda name: first_seen[name]
        )[0]

        print("Votes")

        for name, count in votes.items():
            print(f"{name} -> {count}")

        print("Winner")
        print(winner)
    else:
        print("No valid character-name candidates.")

    print("========================================")

    if winner:
        return {
            "raw": raw_by_name[winner],
            "normalized": winner,
            "method": method_by_name[winner],
            "votes": votes,
            "candidates": candidates
        }

    print("Character Name OCR Failed")

    return None



async def assign_character_roles(thread, api_result):
    # =========================
    # Setup
    # =========================
    guild = thread.guild
    member = thread.owner

    if member is None:
        return

    chars = api_result["characters"]
    tracked_characters = await get_character_configs(guild.id)
    requirement_configs = await get_character_role_requirements(guild.id)

    roles_given = []
    roles_not_given = []

    # =========================
    # Helpers
    # =========================

    async def try_add(role_id,should_have):
        role = guild.get_role(role_id)

        if not role:
            return

        if should_have:

            if role not in member.roles:

                await member.add_roles(
                    role
                )

            roles_given.append(
                role.name
            )

        else:

            roles_not_given.append(
                role.name
            )

    tracked_map = {
        config["character_name"]: config
        for config in tracked_characters
    }

    for requirement in requirement_configs:

        name = requirement["character_name"]
        data = chars.get(name)
        config = tracked_map.get(name)
        role_id = requirement["role_id"]
        role = guild.get_role(role_id)

        if not role:
            continue

        if not data:
            roles_not_given.append(role.name)
            continue

        lc = data["light_cone"]
        superimpose = lc["superimpose"] if lc else 0
        sig_on = has_signature_lc(
            config,
            lc
        )

        should_have = (
            data["eidolons"] >= requirement["required_eidolons"]
            and superimpose >= requirement["required_superimpose"]
            and (
                not requirement["require_signature"]
                or sig_on
            )
            and (
                not requirement["require_max_traces"]
                or data["fully_maxed"]
            )
        )

        await try_add(
            role_id,
            should_have
        )

    # =========================
    # Logs
    # =========================
    print(f"Role audit for {member.name}")
    print("Given:", roles_given)
    print("Not Given:", roles_not_given)

    # =========================
    # Send Result Message
    # =========================
    msg = f"🎭 **Role Update for {member.display_name}**\n\n"

    if roles_given:
        msg += "✅ **Given:**\n• " + "\n• ".join(roles_given) + "\n\n"
    else:
        msg += "✅ **Given:** None\n\n"

    if roles_not_given:
        msg += "❌ **Not Given:**\n• " + "\n• ".join(roles_not_given) + "\n\n"

    msg += f"<a:SparxieMeme:1485677074093048021>\n"
    await thread.send(msg)
    await verification_log(
        guild,
        "Role Audit",
        msg
    )
    return roles_given, roles_not_given

async def assign_custom_roles(thread, api_result, obtained_date, detected_character=None):
    if not obtained_date:
        return

    guild = thread.guild
    member = thread.owner

    if member is None:
        return

    custom_roles = await get_custom_roles(guild.id)
    chars = api_result["characters"]
    roles_given = []
    roles_not_given = []
    normalized_detected_character = (
        normalize_name(detected_character)
        if detected_character
        else None
    )

    for config in custom_roles:
        name = config["character_name"]
        source_type = config["source_type"]

        if source_type not in ("banner_window", "custom_window"):
            continue

        if (
            normalized_detected_character
            and normalize_name(name) != normalized_detected_character
        ):
            continue

        if not chars.get(name):
            roles_not_given.append(
                f"{name} (Character not owned)")
            continue

        try:
            start_date = datetime.date.fromisoformat(
                config["start_date"]
            )
            end_date = datetime.date.fromisoformat(
                config["end_date"]
            )
        except ValueError:
            continue

        if not start_date <= obtained_date <= end_date:
            roles_not_given.append(
                f"{name} (Outside banner window)")
            continue

        role = guild.get_role(config["role_id"])

        if not role:
            roles_not_given.append(
                f"{name} (Discord role deleted)")
            continue

        if role not in member.roles:
            await member.add_roles(role)
            roles_given.append(role.name)
        else:
            roles_given.append(f"{role.name} (Already present)")

    if roles_given:

        msg = (
            f"**Custom Role Update for {member.display_name}**\n"
            f"Obtained Date: `{obtained_date.isoformat()}`\n"
            "Given:\n- " + "\n- ".join(roles_given)
        )
        await thread.send(msg)
        await verification_log(
            guild,
            "OCR Custom Role Granted",
            msg
        )

    return roles_given, roles_not_given

def normalize_name(text):
    text = text.lower()
    return re.sub(r'[^a-z0-9]', '', text)

async def process_thread(thread):
    global stats

    # Step 1: mark as in progress
    await update_thread_tag(thread, "progress_tag")

    stats["checked"] += 1
    api_result = None
    passed = False
    count = 0
    obtained_date = None

    try:
        images = await get_images_from_thread(thread)
        # No images found
        if len(images) == 0:
            stats["failed"] += 1
            await update_thread_tag(thread, "failed_tag")

            await thread.send(
                "⚠️ **No images found** within the last 20 messages of this thread.\n"
                "Please upload a screenshot and try again.\n\n"
                "<a:SparxieMeme:1485677074093048021>"
            )

            print(f"Thread {thread.id}: 0 image(s) found.")
            return
        normalized_images = []
        content_boxes = []

        for img in images:
            norm_img, box = normalize_image(img)
            normalized_images.append(norm_img)
            content_boxes.append(box)

        if normalized_images:
            img = normalized_images[0]
            box = content_boxes[0]

            # Debug normalized image
            img.save(f"debug_normalized_{thread.id}.png")

            # 🔥 DETECT LAYOUT HERE
            orig_size = images[0].size
            layout = detect_layout(img, box, orig_size)

            if layout == "unknown":
                print("⚠️ Layout confidence too low, skipping thread")
                msg = f"⚠️ Unable to Detect Layout confidence too low \n\n"
                msg += f"<a:SparxieMeme:1485677074093048021>\n"
                await thread.send(msg)
                await update_thread_tag(thread, "failed_tag")
                return

            print(f"Detected layout: {layout}")

            # 🔥 DRAW EIDOLON DEBUG OVERLAY HERE
            debug_draw_eidolons(img.copy(), box, layout, thread.id)
            # 🔥 DRAW ROI DEBUG OVERLAYS HERE
            debug_draw_rois(img.copy(), box, layout, thread.id)
            # 🔥 ACTUAL EIDOLON DETECTION TEST
            centers = EIDOLON_ROIS[layout]

            count = 0

            states = []

            for i, center in enumerate(centers):
                crop = get_eidolon_crop(img, box, layout, center)

                crop.save(f"debug_crop_{i}_{thread.id}.png")

                is_lit = is_eidolon_lit(
                    crop,
                    debug=EIDOLON_DEBUG,
                    node_index=i+1
                )

                print(f"Raw Node {i+1}: {'ACTIVE' if is_lit else 'LOCKED'}")
                
                states.append(is_lit)

            # 🔥 ENFORCE ORDER RULE
            for i in range(1, len(states)):
                if not states[i-1]:
                    states[i] = False

            #✅ Prints Final States       
            for i, state in enumerate(states):
                print(f"Final Node {i+1}: {'ACTIVE' if state else 'LOCKED'}")

            count = sum(states)

            print(f"Final States: {states}")
            print(f"Total Eidolons Detected: {count}")

            # 🔥 USE LAYOUT-AWARE ROIs
            rois = extract_rois(img, box, layout)
            debug_save_rois(rois, "roi", thread.id)

            # OCR UID
            print("Starting OCR")
            uid, uid_debug_data = extract_uid_from_image(rois["uid"], thread.id)
            print("Extracted UID:", uid)
            print(">>> About to OCR obtained date")

            try:
                obtained_date, obtained_raw = extract_obtained_date_from_image(
                    rois["obtained_date"],
                    thread.id
                )

                print("Extracted Obtained Date:", obtained_date)
                print("Obtained Date Raw:", obtained_raw)

            except Exception as e:
                print("DATE OCR EXCEPTION:", repr(e))
                import traceback
                traceback.print_exc()

                obtained_date = None
                obtained_raw = None
            api_result = None

            if uid:
                try:
                    tracked_characters=await get_character_configs(thread.guild.id)
                    api_result = await get_character_status(int(uid), tracked_characters)
                    print("Enka Result:", api_result)

                    member = thread.owner

                    enka_name = api_result["nickname"]
                    enka_sig = api_result["signature"]

                    # Normalize Enka values
                    name_compact = normalize_name(enka_name)
                    sig_compact = normalize_name(enka_sig)

                    # Check BOTH nickname + username
                    names_to_check = [
                        member.display_name,   # nickname if exists
                        member.name           # actual username
                    ]

                    normalized_names = [
                        normalize_name(x)
                        for x in names_to_check
                        if x
                    ]

                    ownership_ok = any(
                        n in name_compact or n in sig_compact
                        for n in normalized_names
                        if n
                    )

                    if SKIP_OWNER_CHECK:
                        ownership_ok = True
                        print("⚠️ DEBUG: Owner verification skipped.")

                    if not ownership_ok:
                        stats["failed"] += 1
                        await update_thread_tag(thread, "denied_tag")

                        await thread.send(
                            f"⚠️ Ownership check failed.\n"
                            f"Thread owner: **{thread.owner.display_name}**\n"
                            f"Enka Name: **{api_result['nickname']}**\n"
                            f"Signature: {api_result['signature']}"
                        )
                        return

                    print("✅Passed owner verification")

                    await thread.send(f"✅Passed owner verification\n\n<a:SparxieMeme:1485677074093048021>")

                    chars = api_result["characters"]
                    tracked_characters=await get_character_configs(thread.guild.id)

                    print("Building info message")

                    msg = f"👤Name: **{api_result['nickname']}**\n"
                    msg += f"📝Signature: {api_result['signature']}\n"
                    msg += f"🆔 UID: **{uid}**\n\n"

                    tracked_map={x["character_name"]:x for x in tracked_characters}
                    for name,data in chars.items():
                        data = chars.get(name)

                        if not data:
                            msg += f"**{name}**: ❌ Not Found\n\n"
                            continue

                        lc = data["light_cone"]

                        # Signature LC check
                        config=tracked_map.get(name)
                        sig_on=has_signature_lc(
                            config,
                            lc
                        )

                        sig_text=(
                            "✅ On"
                            if sig_on
                            else "❌ Off"
                        )



                        # LC text
                        if lc:
                            lc_text = f"{lc['name']} (S{lc['superimpose']})"
                        else:
                            lc_text = "None"

                        # Traces text
                        if data["fully_maxed"]:
                            trace_text = "✅ Maxed"
                        else:
                            locked_issue = None
                            other_issues = []

                            for item in data["issues"]:
                                if item.startswith("Locked trace nodes"):
                                    locked_issue = item
                                else:
                                    other_issues.append(item)

                            parts = []

                            if locked_issue:
                                parts.append(f"• {locked_issue}")

                            for item in other_issues:
                                parts.append(f"• {item}")

                            trace_text = "❌ Missing:\n" + "\n".join(parts)

                        msg += (
                            f"**{name}**\n"
                            f"Eidolons: E{data['eidolons']}\n"
                            f"Traces: {trace_text}\n"
                            f"Light Cone: {lc_text}\n"
                            f"Signature LC: {sig_text}\n\n"
                        )
                    msg += f"<a:SparxieMeme:1485677074093048021>\n"

                    print("Finished info message")
                    print("Sending info message")
                    print("Message Length:", len(msg))
                    await thread.send(msg)

                except Exception as e:
                    print("Enka Fetch Failed:", e)
            else:
                stats["failed"] += 1
                await update_thread_tag(thread, "failed_tag")
                await thread.send(
                    "⚠️ **OCR Failed**\n"
                    f"```text\n{format_uid_ocr_debug(uid_debug_data)}\n```\n"
                    "Detected UID: `None`\n"
                    "Please send a clearer screenshot.\n\n"
                    "<a:SparxieMeme:1485677074093048021>")
                print("No UID detected")
                return


        print(
            f"Thread {thread.id}: "
            f"{len(images)} image(s) normalized to 1920x1080"
            )


        # 🔧 PLACEHOLDER RESULT (Step 4+ will replace this)
        passed = False

        if api_result:

            chars=api_result["characters"]

            passed=any(

                data is not None

                for data in chars.values()

            )

        if passed:
            stats["passed"] += 1
            await update_thread_tag(thread, "approved_tag")
            character_given, character_not_given = (
                await assign_character_roles(
                    thread,
                    api_result
                )
            )

            custom_given = []
            custom_not_given = []

            if obtained_date:

                custom_given, custom_not_given = (
                    await assign_custom_roles(
                        thread,
                        api_result,
                        obtained_date
                    )
                )
            print("\n========== ROLE AUDIT ==========")

            print("\nCharacter Roles Given:")
            for role in character_given:
                print(f"  ✅ {role}")

            print("\nCharacter Roles Not Given:")
            for role in character_not_given:
                print(f"  ❌ {role}")

            print("\nCustom OCR Roles Given:")
            for role in custom_given:
                print(f"  ✅ {role}")

            print("\nCustom OCR Roles Not Given:")
            for role in custom_not_given:
                print(f"  ❌ {role}")

            print("================================\n")
        else:
            stats["failed"] += 1
            await update_thread_tag(thread, "denied_tag")


    except Exception as e:
        stats["failed"] += 1
        await update_thread_tag(thread, "failed_tag")
        print(f"Error processing thread {thread.id}: {e}")

def has_lock_icon(crop):
    w, h = crop.size

    # 🔥 SHIFT LEFT (THIS IS THE KEY FIX)
    region = crop.crop((
        int(w * 0.10),   # LEFT SIDE
        int(h * 0.30),
        int(w * 0.45),
        int(h * 0.70)
    ))

    pixels = list(region.getdata())

    dark = 0
    gray = 0
    bright = 0

    for (r, g, b) in pixels:
        brightness = (r + g + b) / 3
        diff = max(r, g, b) - min(r, g, b)

        if brightness < 140:
            dark += 1

        if diff < 30:
            gray += 1

        if brightness > 200:
            bright += 1


    total = len(pixels)

    dark_ratio = dark / total
    gray_ratio = gray / total
    bright_ratio = bright / total

    if EIDOLON_DEBUG:
        print(f"[LOCK DEBUG] dark={dark_ratio:.3f}, gray={gray_ratio:.3f}, bright={bright_ratio:.3f}")

    # 🔥 stricter condition to avoid Node 1 false positive
    return (
        dark_ratio > 0.35 and
        gray_ratio > 0.60 and
        bright_ratio < 0.10   # locks don’t glow
    )


def is_eidolon_lit(crop, debug=False, node_index=None):
    original_crop = crop  # 🔥 keep full image

    crop = crop.crop((
        int(crop.size[0] * EIDOLON_CENTER_CROP),
        int(crop.size[1] * EIDOLON_CENTER_CROP),
        int(crop.size[0] * EIDOLON_CENTER_CROP_END),
        int(crop.size[1] * EIDOLON_CENTER_CROP_END)
    ))

    pixels = list(crop.getdata())

    color_score = 0
    variance_score = 0
    bright = 0
    dark = 0

    for (r, g, b) in pixels:
        diff = max(r, g, b) - min(r, g, b)

        if diff > EIDOLON_COLOR_DIFF_THRESHOLD:
            color_score += 1

        if max(abs(r - g), abs(g - b), abs(r - b)) > EIDOLON_VARIANCE_THRESHOLD:
            variance_score += 1

        brightness = (r + g + b) / 3

        if brightness > EIDOLON_BRIGHT_THRESHOLD:
            bright += 1

        if brightness < EIDOLON_DARK_THRESHOLD:
            dark += 1

    total = len(pixels)

    color_ratio = color_score / total
    variance_ratio = variance_score / total
    bright_ratio = bright / total
    dark_ratio = dark / total

    if debug:
        print(
            f"[Node {node_index}] "
            f"color={color_ratio:.3f} "
            f"variance={variance_ratio:.3f} "
            f"(extra: bright={bright_ratio:.3f} dark={dark_ratio:.3f})"
        )

    # 🔥 LOCK DETECTION ON FULL CROP
    if has_lock_icon(original_crop):
        if debug:
            print(f"[Node {node_index}] LOCK ICON DETECTED")
        return False

    # 🔥 MAIN LOGIC (clean + tunable)
    return (
        color_ratio > EIDOLON_COLOR_RATIO and
        variance_ratio > EIDOLON_VARIANCE_RATIO
    )

def get_eidolon_crop(image, content_box, layout, center):
    cx = content_box["x"] + int(center["x"] * content_box["w"])
    cy = content_box["y"] + int(center["y"] * content_box["h"])

    size = int(EIDOLON_BOX_SIZE * content_box["w"])

    return image.crop((
        cx - size,
        cy - size,
        cx + size,
        cy + size
    ))


async def update_thread_tag(thread, tag_key):
    forum = thread.parent
    available_tags = forum.available_tags
    tags = await get_configured_tags(thread.guild.id)
    new_tag_name = tags.get(tag_key, tag_key)

    new_tag = discord.utils.get(available_tags, name=new_tag_name)
    if new_tag is None:
        print(f"Tag not found: {new_tag_name}")
        return

    try:
        await thread.edit(applied_tags=[new_tag])
    except Forbidden:
        print(f"❌ Missing permissions to edit thread {thread.id}")

# =========================
# Getting Images And PreProcessesing
# =========================

async def get_images_from_thread(thread, limit=20):
    images = []

    async for message in thread.history(limit=limit):
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                try:
                    image_bytes = await attachment.read()
                    image = Image.open(io.BytesIO(image_bytes))
                    images.append(image)
                except Exception as e:
                    print(f"Failed to read image in thread {thread.id}: {e}")

    return images

def normalize_image(image, target_size=(1920, 1080)):
    # Fix orientation
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")

    # Resize while keeping aspect ratio
    image.thumbnail(target_size, Image.Resampling.LANCZOS)

    # Create canvas
    canvas = Image.new("RGB", target_size, (0, 0, 0))

    # Compute offsets
    offset_x = (target_size[0] - image.width) // 2
    offset_y = (target_size[1] - image.height) // 2

    # Paste image
    canvas.paste(image, (offset_x, offset_y))

    # THIS is the content box (known, exact)
    content_box = {
        "x": offset_x,
        "y": offset_y,
        "w": image.width,
        "h": image.height
    }

    return canvas, content_box

def detect_layout(image, content_box, orig_size, debug=True):
    x = content_box["x"]
    y = content_box["y"]
    w = content_box["w"]
    h = content_box["h"]

    # =========================
    # Stage 1: PC vs Tablet/Mobile
    # =========================

    left_strip = image.crop((
        x,
        y + int(0.1 * h),
        x + int(0.09 * w),
        y + int(0.8 * h),
    ))

    top_strip = image.crop((
        x + int(0.1 * w),
        y,
        x + int(0.9 * w),
        y + int(0.18 * h),
    ))

    if debug:
        left_strip.save("debug_layout_left.png")
        top_strip.save("debug_layout_top.png")

    def brightness_score(img):
        gray = img.convert("L")
        pixels = list(gray.getdata())
        return sum(pixels) / len(pixels)

    left_score = brightness_score(left_strip)
    top_score = brightness_score(top_strip)

    diff = abs(left_score - top_score)

    print(
        f"Layout detect → left={left_score:.1f}, "
        f"top={top_score:.1f}, diff={diff:.1f}"
    )

    MIN_CONFIDENCE = 6.0

    if diff < MIN_CONFIDENCE:
        return "unknown"

    # Existing PC logic
    if left_score <= top_score:
        return "pc"

    # =========================
    # Stage 2: Tablet vs Mobile
    # =========================
    orig_w, orig_h = orig_size
    ratio = orig_w / orig_h

    print(
        f"Original image size: {orig_w}x{orig_h} "
        f"(ratio={ratio:.3f})"
    )

    # Portrait phone screenshots
    if ratio > 1.8:
        return "mobile"

    return "tablet"


def roi_from_percent(content_box, roi_def):
    x1 = content_box["x"] + int(roi_def["x1"] * content_box["w"])
    y1 = content_box["y"] + int(roi_def["y1"] * content_box["h"])
    x2 = content_box["x"] + int(roi_def["x2"] * content_box["w"])
    y2 = content_box["y"] + int(roi_def["y2"] * content_box["h"])

    left = min(x1, x2)
    right = max(x1, x2)
    top = min(y1, y2)
    bottom = max(y1, y2)

    return (left, top, right, bottom)



def extract_rois(image, content_box, layout):
    extracted = {}
    layout_rois = ROI_DEFS[layout]

    for name, roi_def in layout_rois.items():
        box = roi_from_percent(content_box, roi_def)
        extracted[name] = image.crop(box)

    return extracted



def layouts_match(images):
    if not images:
        return False

    base_size = images[0].size

    for img in images:
        if img.size != base_size:
            return False

    return True

def prepare_structured_data(images):
    normalized = []
    boxes = []

    for img in images:
        n, b = normalize_image(img)
        normalized.append(n)
        boxes.append(b)

    if not layouts_match(normalized):
        return None

    extracted = [
        extract_rois(img, box)
        for img, box in zip(normalized, boxes)
    ]

    return {
        "images": normalized,
        "regions": extracted
    }

# Debug
def debug_save_rois(rois, prefix, thread_id):
    for name, img in rois.items():
        img.save(f"{prefix}_{name}_{thread_id}.png")

def debug_draw_eidolons(image, content_box, layout, thread_id):
    draw = ImageDraw.Draw(image)

    centers = EIDOLON_ROIS[layout]
    size = int(EIDOLON_BOX_SIZE * content_box["w"])

    for i, center in enumerate(centers):
        cx = content_box["x"] + int(center["x"] * content_box["w"])
        cy = content_box["y"] + int(center["y"] * content_box["h"])

        left = cx - size
        right = cx + size
        top = cy - size
        bottom = cy + size

        # Draw rectangle
        draw.rectangle([left, top, right, bottom], outline="red", width=3)

        # Draw index number
        draw.text((cx, cy), str(i+1), fill="yellow")

    image.save(f"debug_eidolons_overlay_{thread_id}.png")

def debug_draw_rois(image, content_box, layout, thread_id):
    draw = ImageDraw.Draw(image)

    colors = {
        "uid": "lime",
        "obtained_date": "cyan",
    }

    for name, roi_def in ROI_DEFS[layout].items():

        left, top, right, bottom = roi_from_percent(
            content_box,
            roi_def
        )

        print(
            f"[{layout}] {name}: "
            f"({left}, {top}) -> ({right}, {bottom}) "
            f"{right-left}x{bottom-top}"
        )

        draw.rectangle(
            [left, top, right, bottom],
            outline=colors.get(name, "red"),
            width=3
        )

        draw.text(
            (left, top - 20),
            name,
            fill=colors.get(name, "red")
        )

    image.save(
        f"debug_roi_overlay_{layout}_{thread_id}.png"
    )


Token = os.getenv("DISCORD_TOKEN")
bot.run(Token)
