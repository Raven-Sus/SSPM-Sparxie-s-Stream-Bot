import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from discord.errors import Forbidden
from PIL import Image, ImageOps
import io
from PIL import ImageDraw
from PIL import ImageFilter
import numpy as np
import pytesseract
import easyocr
import re
from enka_fetcher import get_character_status
import os
from dotenv import load_dotenv
pytesseract.pytesseract.tesseract_cmd = r"D:\Tesseract\tesseract.exe"


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
load_dotenv()
OWNER_ID = int(os.getenv("OWNER_ID"))
VERIFY_LOG_CHANNEL_ID = 1500204947549978636

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    owner_id=OWNER_ID
)

# =========================
# DEBUG SETTINGS
# =========================
EIDOLON_DEBUG = True

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
            "x1": 0.871, "y1": 0.308,
            "x2": 0.986, "y2": 0.350
        }
    },

        "mobile": {
        "uid": {
            "x1": 0.040, "y1": 0.955,
            "x2": 0.132, "y2": 0.985
        },
        "obtained_date": {
            "x1": 0.890, "y1": 0.385,
            "x2": 0.910, "y2": 0.440
        }
    },

    "pc": {
        "uid": {
            "x1": 0.012,    "y1": 0.962,
            "x2": 0.089,    "y2": 0.996
        },
        "obtained_date": {
            "x1": 0.907,    "y1": 0.264,
            "x2": 0.992,    "y2": 0.314
        },
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

stats = {
    "checked": 0,
    "passed": 0,
    "failed": 0
}

# =========================
# FORUM + TAG CONFIG
# =========================

FORUM_CHANNEL_ID = 1463592275106861159

TAG_TO_VERIFY = "Bot Test"
TAG_IN_PROGRESS = "In Progress"
TAG_APPROVED = "Approved"
TAG_DENIED = "Denied"
TAG_FAILED = "Bot Failed"


# =========================
# EVENTS
# =========================

async def setup_hook():
    try:
        await bot.load_extension("jishaku")
        print("jishaku loaded.")
        await bot.load_extension("cogs.admin")
        print("cogs.admin loaded.")
        await bot.load_extension("cogs.fun")
        print("cogs.fun loaded.")
        print("Extensions loaded.")
    except Exception as e:
        print("Extension load failed:", e)

bot.setup_hook = setup_hook

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    # Sync slash commands
    try:
        guild = discord.Object(id=1374656072970665995)
        bot.tree.copy_global_to(guild=guild)
        guild_synced = await bot.tree.sync(guild=guild)
        global_synced = await bot.tree.sync()

        print(f"Guild synced: {len(guild_synced)}")
        print(f"Global synced: {len(global_synced)}")
    except Exception as e:
        print("Slash sync failed:", e)
    bot.loop.create_task(verification_worker())


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

    # Cooldown
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

# =========================
# Forum Scaning and Processing
# =========================

async def scan_forum_posts(guild):
    forum = guild.get_channel(FORUM_CHANNEL_ID)
    if forum is None:
        return

    # forum.threads = active (non-archived) posts
    for thread in forum.threads:
        tag_names = [tag.name for tag in thread.applied_tags]

        if TAG_TO_VERIFY in tag_names:
            await process_thread(thread)

def easyocr_uid(img):
    results = reader.readtext(
        np.array(img),
        detail=0,
        paragraph=False
    )

    text = " ".join(results)
    print("EasyOCR Raw:", repr(text))

    uid = re.sub(r"\D", "", text)

    if len(uid) == 9:
        return uid, text

    if len(uid) > 9:
        return uid[-9:], text

    return None, text

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

        uid = re.sub(r"\D", "", text)

        # Exactly 9 digits = perfect result
        if len(uid) == 9:
            return uid, text.strip()

        # More than 9 digits = likely junk in front
        if len(uid) > 9:
            return uid[-9:], text.strip()

        return None, text.strip()

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

        uid, raw = run_ocr(bw, f"BW-{t}")

        if uid:
            print(f"OCR Success: BW-{t}")
            return uid, raw

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

    uid, raw = run_ocr(gray2, "GRAY")

    if uid:
        print("OCR Success: GRAY")
        return uid, raw

    # =========================
    # Attempt 3: Full Color
    # =========================
    color = uid_img.resize(
        (uid_img.width * scale, uid_img.height * scale),
        Image.Resampling.LANCZOS
    )

    if thread_id:
        color.save(f"debug_uid_color_{thread_id}.png")

    uid, raw = run_ocr(color, "COLOR")

    if uid:
        print("OCR Success: COLOR")
        return uid, raw

    # =========================
    # EasyOCR Fallback
    # =========================
    print("Trying EasyOCR fallback...")

    # Save debug image
    if thread_id:
        easy_img = uid_img.resize(
            (uid_img.width * scale, uid_img.height * scale),
            Image.Resampling.LANCZOS
        )
        easy_img.save(f"debug_uid_easyocr_{thread_id}.png")

    uid, easy_raw = easyocr_uid(uid_img)


    if uid:
        print("OCR Success: EasyOCR")
        return uid, easy_raw

    # =========================
    # All Failed
    # =========================
    print("OCR Failed In All Modes")

    return None, easy_raw

async def assign_character_roles(thread, api_result):
    # =========================
    # Setup
    # =========================
    guild = thread.guild
    member = thread.owner

    if member is None:
        return

    chars = api_result["characters"]

    roles_given = []
    roles_not_given = []

    # =========================
    # Helpers
    # =========================

    def get_role(name):
        return discord.utils.get(guild.roles, name=name)

    async def try_add(role_name, condition):
        role = get_role(role_name)

        if not role:
            roles_not_given.append(f"{role_name} (missing role)")
            return

        if condition:
            if role not in member.roles:
                await member.add_roles(role)

            roles_given.append(role_name)
        else:
            roles_not_given.append(role_name)

    def has_signature_lc(character_name, lc):
        if not lc:
            return False

        if character_name == "Sparkle":
            return lc["name"] == "Earthly Escapade"

        if character_name == "Sparxie":
            return lc["name"] == "Dazzled by a Flowery World"

        return False

    # =========================
    # Character Role Logic
    # =========================
    async def process_character(
        character_name,
        haver_role,
        max_role,
        e0s1_role,
        e6s5_role
    ):
        data = chars.get(character_name)

        # Character not found
        if not data:
            roles_not_given.extend([
                haver_role,
                max_role,
                e0s1_role,
                e6s5_role
            ])
            return

        lc = data["light_cone"]
        sig_on = has_signature_lc(character_name, lc)

        # Base ownership role
        await try_add(haver_role, True)

        # Max traces role
        await try_add(
            max_role,
            data["fully_maxed"]
        )

        # E0S1 role
        await try_add(
            e0s1_role,
            data["eidolons"] >= 0
            and sig_on
            and lc
            and lc["superimpose"] >= 1
        )

        # E6S5 role
        await try_add(
            e6s5_role,
            data["eidolons"] == 6
            and sig_on
            and lc
            and lc["superimpose"] == 5
        )

    # =========================
    # Sparkle Roles
    # =========================
    await process_character(
        "Sparkle",
        "Sparkle Haver",
        "Sparkle Maxed Traces",
        "Sparkle E0S1",
        "Sparkle E6S5"
    )

    # =========================
    # Sparxie Roles
    # =========================
    await process_character(
        "Sparxie",
        "Sparxie Haver",
        "Sparxie Maxed Traces",
        "Sparxie E0S1",
        "Sparxie E6S5"
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

def normalize_name(text):
    text = text.lower()
    return re.sub(r'[^a-z0-9]', '', text)

async def process_thread(thread):
    global stats

    # Step 1: mark as in progress
    await update_thread_tag(thread, TAG_IN_PROGRESS)

    stats["checked"] += 1
    api_result = None
    passed = False
    count = 0

    try:
        images = await get_images_from_thread(thread)
        # No images found
        if len(images) == 0:
            stats["failed"] += 1
            await update_thread_tag(thread, TAG_FAILED)

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
                await update_thread_tag(thread, TAG_FAILED)
                return

            print(f"Detected layout: {layout}")

            # 🔥 DRAW EIDOLON DEBUG OVERLAY HERE
            debug_draw_eidolons(img.copy(), box, layout, thread.id)
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
            uid, raw_text = extract_uid_from_image(rois["uid"], thread.id)
            print("Extracted UID:", uid)
            api_result = None

            if uid:
                try:
                    api_result = await get_character_status(int(uid))
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

                    if not ownership_ok:
                        stats["failed"] += 1
                        await update_thread_tag(thread, TAG_DENIED)

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

                    sparkle = chars.get("Sparkle")
                    sparxie = chars.get("Sparxie")

                    print("Building info message")

                    msg = f"👤Name: **{api_result['nickname']}**\n"
                    msg += f"📝Signature: {api_result['signature']}\n"
                    msg += f"🆔 UID: **{uid}**\n\n"

                    for name in ["Sparkle", "Sparxie"]:
                        data = chars.get(name)

                        if not data:
                            msg += f"**{name}**: ❌ Not Found\n\n"
                            continue

                        lc = data["light_cone"]

                        # Signature LC check
                        sig_on = False
                        sig_text = "❌ Off"

                        if name == "Sparkle" and lc and lc["name"] == "Earthly Escapade":
                            sig_on = True
                            sig_text = "✅ On"

                        if name == "Sparxie" and lc and lc["name"] == "Dazzled by a Flowery World":
                            sig_on = True
                            sig_text = "✅ On"

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
                await update_thread_tag(thread, TAG_FAILED)
                await thread.send(
                    "⚠️ **OCR Failed**\n"
                    f"Raw OCR: `{raw_text if raw_text else 'EMPTY'}`\n"
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
            chars = api_result["characters"]

            sparkle = chars.get("Sparkle")
            sparxie = chars.get("Sparxie")

            # Example rule:
            # Must have Sparkle and Sparxie
            if (sparkle or sparxie):
                passed = True

        if passed:
            stats["passed"] += 1
            await update_thread_tag(thread, TAG_APPROVED)
            await assign_character_roles(thread, api_result)
        else:
            stats["failed"] += 1
            await update_thread_tag(thread, TAG_DENIED)

    except Exception as e:
        stats["failed"] += 1
        await update_thread_tag(thread, TAG_FAILED)
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


async def update_thread_tag(thread, new_tag_name):
    forum = thread.parent
    available_tags = forum.available_tags

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


Token = os.getenv("DISCORD_TOKEN")
bot.run(Token)
