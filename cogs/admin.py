from database.db import (update_settings, save_character, remove_character, get_character_configs, save_character_role, remove_character_role, get_character_roles, save_character_role_requirement, remove_character_role_requirement, get_character_role_requirements, save_custom_role, remove_custom_role, get_custom_roles, get_configured_character_names, get_configured_character_roles, get_configured_requirement_roles, get_configured_custom_roles)
from utils.character_cache import (get_hsr_character, get_hsr_character_names, get_required_trace_count)
import discord
from discord.ext import commands
from discord import app_commands
import datetime
import io
import json
import os
from PIL import Image
import __main__

BANNER_DATES_PATH = os.path.join(
    "data",
    "banner_dates.json"
)

def audit_message(interaction, action, details):
    now = datetime.datetime.now(datetime.timezone.utc)
    unix_ts = int(now.timestamp())

    return (
        f"Administrator: {interaction.user.mention}\n"
        f"Guild: {interaction.guild.name}\n"
        f"Action: {action}\n"
        f"Time: <t:{unix_ts}:F>\n\n"
        f"{details}"
    )

def load_first_banner_window(character_name):
    if not os.path.exists(BANNER_DATES_PATH):
        return None

    with open(
        BANNER_DATES_PATH,
        encoding="utf-8"
    ) as f:
        data=json.load(f)

    character_data=(
        data
        .get("HSR", {})
        .get(character_name)
    )

    if not character_data:
        return None

    return character_data.get(
        "first_banner"
    )

def has_signature_lc(

    config,

    lc

):

    if not lc:
        return False

    expected=(
        config[
            "signature_lightcone_name"
        ]
    )

    return (
        lc["name"]==expected
    )

async def character_autocomplete(interaction: discord.Interaction, current: str):

    names=get_hsr_character_names()

    filtered=[

        x

        for x in names

        if current.lower()

        in x.lower()

    ]

    return [

        app_commands.Choice(

            name=x,

            value=x

        )

        for x in filtered[:25]

    ]

async def configured_character_autocomplete(
    interaction: discord.Interaction,
    current: str
):

    names = await get_configured_character_names(
        interaction.guild.id
    )

    filtered = [

        x

        for x in names

        if current.lower() in x.lower()

    ]

    return [

        app_commands.Choice(

            name=x,

            value=x

        )

        for x in filtered[:25]

    ]

async def configured_legacy_role_autocomplete(
    interaction: discord.Interaction,
    current: str,
):

    namespace = interaction.namespace

    if not namespace.character:
        return []

    roles = await get_configured_character_roles(
        interaction.guild.id,
        namespace.character
    )

    choices = []

    for config in roles:

        role = interaction.guild.get_role(config["role_id"])

        if role:

            display_name = f"🟢 {role.name}"

            if current.lower() not in role.name.lower():
                continue

            role_id = role.id

        else:

            display_name = f"🔴 Deleted Role ({config['role_id']})"

            if (
                current.lower() not in display_name.lower()
                and current.lower() not in str(config["role_id"])
            ):
                continue

            role_id = config["role_id"]

        choices.append(
            app_commands.Choice(
                name=display_name,
                value=str(role_id)
            )
        )

    return choices[:25]

async def configured_requirement_role_autocomplete(
    interaction: discord.Interaction,
    current: str,
):

    namespace = interaction.namespace

    if not namespace.character:
        return []

    roles = await get_configured_requirement_roles(
        interaction.guild.id,
        namespace.character
    )

    choices = []

    for config in roles:

        role = interaction.guild.get_role(config["role_id"])

        if role:

            display_name = f"🟢 {role.name}"

            if current.lower() not in role.name.lower():
                continue

            role_id = role.id

        else:

            display_name = f"🔴 Deleted Role ({config['role_id']})"

            if (
                current.lower() not in display_name.lower()
                and current.lower() not in str(config["role_id"])
            ):
                continue

            role_id = config["role_id"]

        choices.append(
            app_commands.Choice(
                name=display_name,
                value=str(role_id)
            )
        )

    return choices[:25]

async def configured_custom_role_autocomplete(
    interaction: discord.Interaction,
    current: str,
):

    namespace = interaction.namespace

    if not namespace.character:
        return []

    roles = await get_configured_custom_roles(
        interaction.guild.id,
        namespace.character
    )

    choices = []

    for config in roles:

        role = interaction.guild.get_role(config["role_id"])

        if role:

            display_name = f"🟢 {role.name}"

            if current.lower() not in role.name.lower():
                continue

            role_id = role.id

        else:

            display_name = f"🔴 Deleted Role ({config['role_id']})"

            if (
                current.lower() not in display_name.lower()
                and current.lower() not in str(config["role_id"])
            ):
                continue

            role_id = config["role_id"]

        choices.append(
            app_commands.Choice(
                name=display_name,
                value=str(role_id)
            )
        )

    return choices[:25]

class VerificationLogChannelSelect(
    discord.ui.ChannelSelect
):

    def __init__(self):

        super().__init__(

            placeholder=
            "Select verification log channel",

            channel_types=[
                discord.ChannelType.text
            ],

            min_values=1,
            max_values=1
        )


    async def callback(
        self,
        interaction:
        discord.Interaction
    ):

        channel=self.values[0]

        await update_settings(
            interaction.guild.id,
            verification_log_channel_id=
            channel.id
        )


        await interaction.response.send_message(

            f"✅ Log channel saved:\n"
            f"{channel.mention}",

            ephemeral=True
        )

        await __main__.admin_log(
            interaction.guild,
            "Setup Changed",
            audit_message(
                interaction,
                "Verification log channel changed",
                f"Verification Log Channel: {channel.mention}"
            )
        )

class AdminLogChannelSelect(
    discord.ui.ChannelSelect
):

    def __init__(self):

        super().__init__(

            placeholder=
            "Select admin log channel",

            channel_types=[
                discord.ChannelType.text
            ],

            min_values=1,
            max_values=1
        )


    async def callback(
        self,
        interaction:
        discord.Interaction
    ):

        channel=self.values[0]

        await update_settings(
            interaction.guild.id,
            admin_log_channel_id=
            channel.id
        )


        await interaction.response.send_message(

            f"Admin log channel saved:\n"
            f"{channel.mention}",

            ephemeral=True
        )

        await __main__.admin_log(
            interaction.guild,
            "Setup Changed",
            audit_message(
                interaction,
                "Admin log channel changed",
                f"Admin Log Channel: {channel.mention}"
            )
        )

class ForumChannelSelect(
    discord.ui.ChannelSelect
):

    def __init__(self):

        super().__init__(

            placeholder=
            "Select forum channel",

            channel_types=[
                discord.ChannelType.forum
            ],

            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction
    ):

        channel=self.values[0]

        await update_settings(

            interaction.guild.id,

            forum_channel_id=
            channel.id
        )

        await interaction.response.send_message(

            f"✅ Forum saved:\n"
            f"{channel.mention}",

            ephemeral=True
        )

        await __main__.admin_log(
            interaction.guild,
            "Setup Changed",
            audit_message(
                interaction,
                "Forum channel changed",
                f"Forum Channel: {channel.mention}"
            )
        )

class SetupView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=300
        )

        self.add_item(
            VerificationLogChannelSelect()
        )

        self.add_item(
            AdminLogChannelSelect()
        )

        self.add_item(
            ForumChannelSelect()
        )

        self.add_item(
            ConfigureTagsButton()
        )

class ConfigureTagsButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(

            label=
            "Configure Tags",

            style=
            discord.ButtonStyle.blurple
        )

    async def callback(
        self,
        interaction
    ):

        await interaction.response.send_modal(
            TagModal()
        )

class TagModal(
    discord.ui.Modal,
    title="Tag Setup"
):

    verify=discord.ui.TextInput(
        label="Verify Tag",
        default="Bot Test"
    )

    progress=discord.ui.TextInput(
        label="In Progress Tag",
        default="In Progress"
    )

    approved=discord.ui.TextInput(
        label="Approved Tag",
        default="Approved"
    )

    denied=discord.ui.TextInput(
        label="Denied Tag",
        default="Denied"
    )

    failed=discord.ui.TextInput(
        label="Bot Failed Tag",
        default="Bot Failed"
    )

    async def on_submit(
        self,
        interaction
    ):

        await update_settings(

            interaction.guild.id,

            verify_tag=
            str(self.verify),

            progress_tag=
            str(self.progress),

            approved_tag=
            str(self.approved),

            denied_tag=
            str(self.denied),

            failed_tag=
            str(self.failed)

        )

        await interaction.response.send_message(

            "✅ Tags saved",

            ephemeral=True
        )
        await __main__.admin_log(
            interaction.guild,
            "Tag Configuration Changed",
            audit_message(
                interaction,
                "Tag configuration changed",
                (
                    f"Verify Tag: {self.verify}\n"
                    f"Progress Tag: {self.progress}\n"
                    f"Approved Tag: {self.approved}\n"
                    f"Denied Tag: {self.denied}\n"
                    f"Failed Tag: {self.failed}"
                )
            )
        )


############################
#-------- Commands --------#
############################

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="start", description="Start verification scanning")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    async def start(self, interaction: discord.Interaction):
        import __main__

        if __main__.verification_enabled:
            await interaction.response.send_message(
                "⚠️ Verification is already running.",
                ephemeral=True
            )
            return

        __main__.verification_enabled = True
        __main__.stats = {"checked": 0, "passed": 0, "failed": 0}

        await interaction.response.send_message("✅ Verification started.")

    @app_commands.command(name="stop", description="Stop verification scanning")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    async def stop(self, interaction: discord.Interaction):
        import __main__

        if not __main__.verification_enabled:
            await interaction.response.send_message(
                "⚠️ Verification is not running.",
                ephemeral=True
            )
            return

        __main__.verification_enabled = False

        s = __main__.stats

        await interaction.response.send_message(
            f"🛑 Verification stopped.\n"
            f"Checked: {s['checked']}\n"
            f"Passed: {s['passed']}\n"
            f"Failed: {s['failed']}"
        )

    @app_commands.command(
        name="verify",
        description="Verify manually using your UID"
    )
    @app_commands.guild_only()
    async def verify(
        self,
        interaction: discord.Interaction,
        uid: str,
        image1: discord.Attachment = None,
        image2: discord.Attachment = None,
        image3: discord.Attachment = None,
        image4: discord.Attachment = None
    ):
        import __main__

        await interaction.response.defer(ephemeral=True)

        try:
            uid_int = int(uid)
        except:
            await interaction.followup.send(
                "❌ UID must be numbers only." , ephemeral=True
            )
            return

        # Fetch Enka
        try:
            tracked_characters=await __main__.get_character_configs(interaction.guild.id)
            api_result = await __main__.get_character_status(uid_int, tracked_characters)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to fetch UID.\n{e}" , ephemeral=True
            )
            return

        obtained_date = None
        obtained_raw = None
        member = interaction.user

        now = datetime.datetime.now(datetime.timezone.utc)
        unix_ts = int(now.timestamp())

        log_header = (
            f"📝 **Manual Verify Used**\n"
            f"👤 User: {member.mention}\n"
            f"📛 Name: {member.display_name}\n"
            f"🆔 UID: `{uid}`\n"
            f"📍 Channel: {interaction.channel.mention}\n"
            f"🕒 Time: <t:{unix_ts}:F>\n"
            f"⏱️ Relative: <t:{unix_ts}:R>\n\n"
        )

        # =========================
        # OWNER CHECK
        # =========================
        print(">>> Starting owner verification")
        enka_name = api_result["nickname"]
        enka_sig = api_result["signature"]

        name_compact = __main__.normalize_name(enka_name)
        sig_compact = __main__.normalize_name(enka_sig)

        names_to_check = [
            member.display_name,
            member.name
        ]

        normalized_names = [
            __main__.normalize_name(x)
            for x in names_to_check
            if x
        ]

        ownership_ok = any(
            n in name_compact or n in sig_compact
            for n in normalized_names
            if n
        )
        if __main__.SKIP_OWNER_CHECK:
            ownership_ok = True
            print("⚠️ DEBUG: Owner verification skipped.")

        if not ownership_ok:

            fail_msg = (
                log_header +
                "⚠️ **Ownership Check Failed**\n"
                f"Discord Name: **{member.display_name}**\n"
                f"Enka Name: **{enka_name}**\n"
                f"Signature: {enka_sig}"
            )

            await __main__.verification_log(
                interaction.guild,
                "Ownership Failed",
                fail_msg
            )

            await interaction.followup.send(
                f"⚠️ Ownership check failed.\n"
                f"Discord Name: **{member.display_name}**\n"
                f"Enka Name: **{enka_name}**\n"
                f"Signature: {enka_sig}" , ephemeral=True
            )
            return

        # Passed ownership
        await interaction.followup.send(
            "✅ Passed owner verification.\n\n"
            "<a:SparxieMeme:1485677074093048021>", ephemeral=True
        )
        await __main__.verification_log(
            interaction.guild,
            "Verification Passed",
            log_header +
            "Passed Owner Verification"
        )

        images = [
            image
            for image in (image1, image2, image3, image4)
            if image is not None
        ]
        image_results = []
        custom_role_requests = []

        enka_character_map = {
            __main__.normalize_name(name): (name, data)
            for name, data in api_result["characters"].items()
        }

        verify_slot_acquired = False
        verify_request_id = interaction.id

        if images:
            try:
                (
                    should_wait,
                    queue_position,
                    active_count,
                    verify_slot_acquired
                ) = await __main__.enter_verify_queue(
                    interaction.guild.id,
                    verify_request_id
                )
    
                if should_wait:
                    await interaction.followup.send(
                        "⏳ Verification queue\n\n"
                        f"You are #{queue_position} in the queue for this server.\n"
                        f"There are {active_count} verifications currently being processed.",
                        ephemeral=True
                    )
    
                if not verify_slot_acquired:
                    await __main__.acquire_verify_slot(
                        interaction.guild.id,
                        verify_request_id
                    )
                    verify_slot_acquired = True
                for image_index, image in enumerate(images, start=1):
                    image_debug_id = f"{interaction.id}_{image_index}"
                    image_lines = [f"Image {image_index}:"]
        
                    print(f"===== VERIFY IMAGE {image_index} =====")
        
                    try:
                        image_bytes = await image.read()
                        source_image = Image.open(
                            io.BytesIO(image_bytes)
                        )
                        norm_img, box = __main__.normalize_image(source_image)
                        layout = __main__.detect_layout(
                            norm_img,
                            box,
                            source_image.size
                        )
        
                        print(f"Detected layout: {layout}")
        
                        if layout == "unknown":
                            image_lines.append("Screenshot layout could not be detected.")
                            print("==========================")
                            image_results.append("\n".join(image_lines))
                            continue
        
                        __main__.debug_draw_rois(
                            norm_img.copy(),
                            box,
                            layout,
                            image_debug_id
                        )
        
                        rois = __main__.extract_rois(
                            norm_img,
                            box,
                            layout
                        )
        
                        print(">>> About to OCR UID")
                        ocr_uid, uid_debug_data = __main__.extract_uid_from_image(
                            rois["uid"],
                            image_debug_id
                        )
                        print(f">>> UID OCR Finished: {ocr_uid}")
                        matched_uid = __main__.find_matching_uid_candidate(
                            uid,
                            uid_debug_data
                        )
                        uid_ocr_summary = __main__.format_uid_ocr_debug(
                            uid_debug_data
                        )
        
                        print(f"UID OCR: {ocr_uid}")
        
                        if matched_uid is None and ocr_uid is None:
                            await __main__.verification_log(
                                interaction.guild,
                                "UID OCR Failed",
                                log_header +
                                f"UID OCR Failed - Image {image_index}\n"
                                f"Typed UID: `{uid}`\n"
                                f"```text\n{uid_ocr_summary}\n```\n"
                                "Image Attached: Yes\n"
                            )
                            image_lines.append("Could not read the UID from this screenshot.")
                            print("==========================")
                            image_results.append("\n".join(image_lines))
                            continue
        
                        if matched_uid is None:
                            await __main__.verification_log(
                                interaction.guild,
                                "UID Screenshot Mismatch",
                                log_header +
                                f"UID Screenshot Mismatch - Image {image_index}\n"
                                f"Typed UID: `{uid}`\n"
                                f"Screenshot UID: `{ocr_uid}`\n"
                                f"```text\n{uid_ocr_summary}\n```\n"
                                "Image Attached: Yes\n"
                            )
                            image_lines.append("The UID in this screenshot does not match the UID you entered.")
                            image_lines.append(f"Typed UID: `{uid}`")
                            image_lines.append(f"Screenshot UID: `{ocr_uid}`")
                            print("==========================")
                            image_results.append("\n".join(image_lines))
                            continue
        
                        image_lines.append("UID matched")
        
                        print(">>> About to OCR CHARACTER NAME")
                        ocr_name = __main__.extract_name_from_image(
                            rois["name"],
                            image_debug_id
                        )
                        print(f">>> CHARACTER NAME OCR Finished: {ocr_name}")
        
                        if not ocr_name:
                            image_lines.append("Could not read the character name from this screenshot.")
                            print("Character OCR: None")
                            print("Character verification FAILED")
                            print("==========================")
                            image_results.append("\n".join(image_lines))
                            continue
        
                        detected_character = ocr_name["normalized"]
                        matched_character, matched_character_data = enka_character_map.get(
                            detected_character,
                            (None, None)
                        )
        
                        print(f"Character OCR: {ocr_name['raw']}")
                        print(f"Character OCR normalized: {detected_character}")
                        print(f"Character OCR winner method: {ocr_name.get('method')}")
                        print("Character OCR votes:")
                        for name, count in ocr_name.get("votes", {}).items():
                            print(f"    {name} -> {count}")
                        print(f"Enka character match: {matched_character or 'NONE'}")
                        print(
                            "Enka character data: "
                            f"{'PRESENT' if matched_character_data is not None else 'MISSING'}"
                        )
        
                        if matched_character is None or matched_character_data is None:
                            image_lines.append(f"Character: {ocr_name['raw']}")
                            image_lines.append(
                                "The character shown in this screenshot does not match a character owned by this UID."
                            )
                            print("Character verification FAILED")
                            print("==========================")
                            image_results.append("\n".join(image_lines))
                            continue
        
                        image_lines.append(f"Character: {matched_character}")
                        image_lines.append("Character belongs to UID")
        
                        print(">>> About to OCR Obtained Date")
        
                        try:
                            obtained_date, obtained_raw = (
                                __main__.extract_obtained_date_from_image(
                                    rois["obtained_date"],
                                    image_debug_id
                                )
                            )
        
                            print(f">>> Obtained Date: {obtained_date}")
                            print(f">>> Raw Date OCR: {obtained_raw}")
        
                        except Exception as e:
                            import traceback
        
                            print("!!!!! DATE OCR CRASHED !!!!!")
                            traceback.print_exc()
        
                            obtained_date = None
                            obtained_raw = str(e)
        
                        print(
                            "Obtained date: "
                            f"{obtained_date.isoformat() if obtained_date else 'None'}"
                        )
        
                        if obtained_date:
                            image_lines.append(
                                f"Obtained Date: {obtained_date.isoformat()}"
                            )
                            custom_role_requests.append(
                                (len(image_results), obtained_date, detected_character)
                            )
                        else:
                            image_lines.append("Date could not be read")
        
                    except Exception as e:
                        obtained_raw = f"OCR image failed: {e}"
                        image_lines.append(f"OCR image failed: {e}")
        
                    print("==========================")
                    image_results.append("\n".join(image_lines))
        
                print(">>> Finished OCR image section")

            finally:
                if verify_slot_acquired:
                    await __main__.release_verify_slot(interaction.guild.id)
                else:
                    await __main__.leave_verify_queue(
                        interaction.guild.id,
                        verify_request_id
                    )


        # =========================
        # CHARACTER INFO MESSAGE
        # =========================
        chars = api_result["characters"]

        msg = f"👤Name: **{api_result['nickname']}**\n"
        msg += f"📝Signature: {api_result['signature']}\n"
        msg += f"🆔 UID: **{uid}**\n\n"

        tracked_map={
            x["character_name"]:x
            for x in tracked_characters}

        for name,data in chars.items():
            data = chars.get(name)

            if not data:
                msg += f"**{name}**: ❌ Not Found\n\n"
                continue

            lc = data["light_cone"]

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

            if lc:
                lc_text = f"{lc['name']} (S{lc['superimpose']})"
            else:
                lc_text = "None"

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

        msg += "<a:SparxieMeme:1485677074093048021>"

        await __main__.verification_log(
            interaction.guild,
            "Manual Verify",
            log_header + msg
        )

        await interaction.followup.send(
        msg,
        ephemeral=True)
       

        # =========================
        # ROLE ASSIGNMENT
        # =========================
        async def dual_send(self, content):
            await interaction.followup.send(
                content,
                ephemeral=True
            )


        fake_thread = type(
            "FakeThread",
            (),
            {
                "guild": interaction.guild,
                "owner": member,
                "send": dual_send
            }
        )()

        await __main__.assign_character_roles(
            fake_thread,
            api_result
        )

        for result_index, request_date, detected_character in custom_role_requests:
            custom_given, custom_not_given = await __main__.assign_custom_roles(
                fake_thread,
                api_result,
                request_date,
                detected_character
            )

            if custom_given:
                image_results[result_index] += (
                    "\nCustom Role Given:\n- "
                    + "\n- ".join(custom_given)
                )
            else:
                image_results[result_index] += "\nCustom Role Given: None"

            if custom_not_given:
                image_results[result_index] += (
                    "\nCustom Role Not Given:\n- "
                    + "\n- ".join(custom_not_given)
                )

        if images and not custom_role_requests:
            await interaction.followup.send(
                "No readable obtained dates were found in the uploaded images, so custom date roles were skipped.",
                ephemeral=True
            )

        if image_results:
            chunks = []
            current = ""

            for result in image_results:
                addition = result if not current else "\n\n" + result

                if len(current) + len(addition) > 1700:
                    chunks.append(current)
                    current = result
                else:
                    current += addition

            if current:
                chunks.append(current)

            for chunk in chunks:
                await interaction.followup.send(
                    chunk,
                    ephemeral=True
                )

            for chunk in chunks:
                await __main__.verification_log(
                    interaction.guild,
                    "Manual Verify Image Results",
                    log_header + chunk
                )
    



    @app_commands.command(name="add_5star", description="Add tracked 5-star")
    @app_commands.autocomplete(character=character_autocomplete)
    @app_commands.default_permissions(administrator=True)

    async def add_5star(

        self,

        interaction:
        discord.Interaction,

        character:str

    ):

        data=get_hsr_character(
            character
        )

        if not data:

            await interaction.response.send_message(

                "❌ Character not found",

                ephemeral=True
            )

            return


        path=data["path"]

        traces=(
            get_required_trace_count(
                path
            )
        )

        signature=(
            data["signature_lc"]
        )

        if not signature:

            await interaction.response.send_message(

                "❌ No signature LC found.\n"
                "Use /add_4star instead.",

                ephemeral=True
            )

            return


        await save_character(

            interaction.guild.id,

            "HSR",

            data["name"],

            data["id"],

            path,

            traces,

            signature
        )

        await interaction.response.send_message(

    f"""

    ✅ 5-Star Added

    Character:
    {data['name']}

    Path:
    {path}

    Required Traces:
    {traces}

    Signature LC:
    {signature}

    """,

    ephemeral=True
    )

        await __main__.admin_log(
            interaction.guild,
            "Character Added",
            audit_message(
                interaction,
                "5-star character added",
                (
                    f"Character: {data['name']}\n"
                    f"Game: HSR\n"
                    f"Path: {path}\n"
                    f"Required Traces: {traces}\n"
                    f"Signature LC: {signature}"
                )
            )
        )

    @app_commands.command(name="add_4star", description="Add tracked 4-star")
    @app_commands.autocomplete(character=character_autocomplete)
    @app_commands.default_permissions(administrator=True)

    async def add_4star(

        self,

        interaction:
        discord.Interaction,

        character:str,

        light_cone:str

    ):

        data=get_hsr_character(
            character
        )

        if not data:

            await interaction.response.send_message(

                "❌ Character not found",

                ephemeral=True
            )

            return


        path=data["path"]

        traces=(
            get_required_trace_count(
                path
            )
        )


        await save_character(

            interaction.guild.id,

            "HSR",

            data["name"],

            data["id"],

            path,

            traces,

            light_cone
        )

        await interaction.response.send_message(

    f"""

    ✅ 4-Star Added

    Character:
    {data['name']}

    Path:
    {path}

    Required Traces:
    {traces}

    Chosen LC:
    {light_cone}

    """,

    ephemeral=True
    )

        await __main__.admin_log(
            interaction.guild,
            "Character Added",
            audit_message(
                interaction,
                "4-star character added",
                (
                    f"Character: {data['name']}\n"
                    f"Game: HSR\n"
                    f"Path: {path}\n"
                    f"Required Traces: {traces}\n"
                    f"Chosen LC: {light_cone}"
                )
            )
        )

    @app_commands.command(name="remove_character", description="Remove tracked character")
    @app_commands.autocomplete(character=configured_character_autocomplete)
    @app_commands.default_permissions(administrator=True)

    async def remove_character_cmd(

        self,

        interaction:
        discord.Interaction,

        character:str

    ):

        cleaned=(
            character
            .rsplit(" (",1)[0]
        )

        await remove_character(

            interaction.guild.id,

            cleaned
        )

        await interaction.response.send_message(

            f"🗑 Removed:\n{cleaned}",

            ephemeral=True
        )

        await __main__.admin_log(
            interaction.guild,
            "Character Removed",
            audit_message(
                interaction,
                "Character removed",
                f"Character: {cleaned}"
            )
        )

    @app_commands.command(name="setup", description="Configure bot")
    @app_commands.default_permissions(administrator=True)
    async def setup(
        self,
        interaction:
        discord.Interaction
        ):

        embed=discord.Embed(

            title=
            "⚙ Verification Setup",

            description=(

                "Choose verification logs, "
                "admin logs, forum channel, "
                "and tag configuration below."

            )
        )

        await interaction.response.send_message(embed=embed, view=SetupView(), ephemeral=True)

        await __main__.admin_log(
            interaction.guild,
            "Setup Opened",
            audit_message(
                interaction,
                "Setup command opened",
                "Setup UI sent."
            )
        )

    # Legacy role mapping command kept temporarily for migration safety.
    @app_commands.command(name="set_role", description="Legacy: configure old role rewards")
    @app_commands.default_permissions(administrator=True)
    @app_commands.autocomplete(character=configured_character_autocomplete)
    @app_commands.choices(

        role_type=[

            app_commands.Choice(
                name="Haver",
                value="haver"
            ),

            app_commands.Choice(
                name="Maxed",
                value="maxed"
            ),

            app_commands.Choice(
                name="E0S1",
                value="e0s1"
            ),

            app_commands.Choice(
                name="E6S5",
                value="e6s5"
            )

        ]
    )

    async def set_role(

        self,

        interaction:
        discord.Interaction,

        character:str,

        role_type:str,

        role:discord.Role

    ):

        cleaned=(
            character
            .rsplit(" (",1)[0]
        )

        await save_character_role(

            interaction.guild.id,

            cleaned,

            role_type,

            role.id
        )

        await interaction.response.send_message(

    f"""

    ✅ Role Saved

    Character:
    {cleaned}

    Type:
    {role_type}

    Role:
    {role.mention}

    """,

    ephemeral=True
    )

        await __main__.admin_log(
            interaction.guild,
            "Legacy Character Role Added",
            audit_message(
                interaction,
                "Legacy character role mapping added",
                (
                    f"Character: {cleaned}\n"
                    f"Legacy Type: {role_type}\n"
                    f"Role: {role.mention}"
                )
            )
        )

    # Legacy role mapping command kept temporarily for migration safety.
    @app_commands.command(name="remove_role", description="Legacy: remove old configured role")
    @app_commands.default_permissions(administrator=True)
    @app_commands.autocomplete(character=configured_character_autocomplete)
    @app_commands.choices(
        role_type=[
            app_commands.Choice(
                name="Haver",
                value="haver"
            ),
            app_commands.Choice(
                name="Maxed",
                value="maxed"
            ),
            app_commands.Choice(
                name="E0S1",
                value="e0s1"
            ),
            app_commands.Choice(
                name="E6S5",
                value="e6s5"
            )
        ]
    )
    async def remove_role(

        self,

        interaction:
        discord.Interaction,

        character:str,

        role_type:str

    ):

        cleaned = (
            character
            .rsplit(" (",1)[0]
        )

        await remove_character_role(

            interaction.guild.id,

            cleaned,

            role_type
        )

        await interaction.response.send_message(

            f"🗑 Removed role config\n"
            f"Character: {cleaned}\n"
            f"Type: {role_type}",

            ephemeral=True
        )

        await __main__.admin_log(
            interaction.guild,
            "Legacy Character Role Removed",
            audit_message(
                interaction,
                "Legacy character role mapping removed",
                (
                    f"Character: {cleaned}\n"
                    f"Legacy Type: {role_type}"
                )
            )
        )

    @app_commands.command(name="set_character_role", description="Configure a character role requirement")
    @app_commands.default_permissions(administrator=True)
    @app_commands.autocomplete(character=configured_character_autocomplete)
    async def set_character_role(

        self,

        interaction:
        discord.Interaction,

        character:str,

        role:discord.Role,

        required_eidolons:app_commands.Range[int, 0, 6],

        required_superimpose:app_commands.Range[int, 0, 5],

        require_signature:bool,

        require_max_traces:bool

    ):

        cleaned=(
            character
            .rsplit(" (",1)[0]
        )

        await save_character_role_requirement(
            interaction.guild.id,
            cleaned,
            role.id,
            required_eidolons,
            required_superimpose,
            require_signature,
            require_max_traces
        )

        await interaction.response.send_message(
            f"Character role requirement saved.\n"
            f"Character: {cleaned}\n"
            f"Role: {role.mention}\n"
            f"Eidolons: E{required_eidolons}+\n"
            f"Superimpose: S{required_superimpose}+\n"
            f"Require Signature: {require_signature}\n"
            f"Require Max Traces: {require_max_traces}",
            ephemeral=True
        )

        await __main__.admin_log(
            interaction.guild,
            "Character Role Added",
            audit_message(
                interaction,
                "Character role requirement added",
                (
                    f"Character: {cleaned}\n"
                    f"Role: {role.mention}\n"
                    f"Required Eidolons: E{required_eidolons}+\n"
                    f"Required Superimpose: S{required_superimpose}+\n"
                    f"Require Signature: {require_signature}\n"
                    f"Require Max Traces: {require_max_traces}"
                )
            )
        )

    @app_commands.command(name="remove_character_role", description="Remove a character role requirement")
    @app_commands.default_permissions(administrator=True)
    @app_commands.autocomplete(character=configured_character_autocomplete, role=configured_requirement_role_autocomplete)
    async def remove_character_role(

        self,

        interaction:
        discord.Interaction,

        character:str,

        role:str

    ):

        cleaned=(
            character
            .rsplit(" (",1)[0]
        )

        await remove_character_role_requirement(
            interaction.guild.id,
            cleaned,
            int(role)
        )

        discord_role = interaction.guild.get_role(int(role))

        role_display = (
            discord_role.mention
            if discord_role
            else f"🔴 Deleted Role ({role})"
        )

        await interaction.response.send_message(
            f"Character role requirement removed.\n"
            f"Character: {cleaned}\n"
            f"Role: {role_display}",
            ephemeral=True
        )

        await __main__.admin_log(
            interaction.guild,
            "Character Role Removed",
            audit_message(
                interaction,
                "Character role requirement removed",
                (
                    f"Character: {cleaned}\n"
                    f"Role: {role_display}"
                )
            )
        )

    @app_commands.command(name="set_custom_role", description="Configure an OCR/date based custom role")
    @app_commands.default_permissions(administrator=True)
    @app_commands.autocomplete(character=configured_character_autocomplete)
    @app_commands.choices(
        source_type=[
            app_commands.Choice(name="Banner Window", value="banner_window"),
            app_commands.Choice(name="Custom Window", value="custom_window"),
            app_commands.Choice(name="Manual", value="manual")
        ]
    )
    async def set_custom_role(

        self,

        interaction:
        discord.Interaction,

        character:str,

        role:discord.Role,

        source_type:str,

        start_date:str = None,

        end_date:str = None

    ):

        cleaned=(
            character
            .rsplit(" (",1)[0]
        )

        if source_type == "banner_window":
            banner_window=load_first_banner_window(
                cleaned
            )

            if not banner_window:
                await interaction.response.send_message(
                    "No first banner window found for this character.",
                    ephemeral=True
                )
                return

            start_date=banner_window["start"]
            end_date=banner_window["end"]

        elif source_type in ("custom_window", "manual"):
            if not start_date or not end_date:
                await interaction.response.send_message(
                    "Start date and end date are required for this source type.",
                    ephemeral=True
                )
                return

            try:
                datetime.date.fromisoformat(start_date)
                datetime.date.fromisoformat(end_date)
            except ValueError:
                await interaction.response.send_message(
                    "Dates must use YYYY-MM-DD format.",
                    ephemeral=True
                )
                return

        await save_custom_role(
            interaction.guild.id,
            cleaned,
            role.id,
            start_date,
            end_date,
            source_type
        )

        await interaction.response.send_message(
            f"Custom role saved.\n"
            f"Character: {cleaned}\n"
            f"Role: {role.mention}\n"
            f"Window: {start_date} to {end_date}\n"
            f"Source: {source_type}",
            ephemeral=True
        )

        await __main__.admin_log(
            interaction.guild,
            "Custom Role Added",
            audit_message(
                interaction,
                "Custom role added",
                (
                    f"Character: {cleaned}\n"
                    f"Role: {role.mention}\n"
                    f"Window: {start_date} to {end_date}\n"
                    f"Source: {source_type}"
                )
            )
        )

    @app_commands.command(name="remove_custom_role", description="Remove an OCR/date based custom role")
    @app_commands.default_permissions(administrator=True)
    @app_commands.autocomplete(character=configured_character_autocomplete, role=configured_custom_role_autocomplete)
    async def remove_custom_role_cmd(

        self,

        interaction:
        discord.Interaction,

        character:str,

        role:str

    ):

        cleaned=(
            character
            .rsplit(" (",1)[0]
        )

        await remove_custom_role(
            interaction.guild.id,
            cleaned,
            int(role)
        )

        discord_role = interaction.guild.get_role(int(role))


        role_display = (
            discord_role.mention
            if discord_role
            else f"🔴 Deleted Role ({role})"
        )

        await interaction.response.send_message(
            f"Custom role removed.\n"
            f"Character: {cleaned}\n"
            f"Role: {role_display}",
            ephemeral=True
        )

        await __main__.admin_log(
            interaction.guild,
            "Custom Role Removed",
            audit_message(
                interaction,
                "Custom role removed",
                (
                    f"Character: {cleaned}\n"
                    f"Role: {role_display}"
                )
            )
        )

    @app_commands.command(name="list_characters", description="List tracked characters")
    @app_commands.default_permissions(administrator=True)
    async def list_characters(

        self,

        interaction:
        discord.Interaction

    ):

        characters=await get_character_configs(
            interaction.guild.id
        )

        if not characters:
            await interaction.response.send_message(
                "No tracked characters configured.",
                ephemeral=True
            )
            return

        lines=[
            (
                f"- {character['character_name']} "
                f"({character['game']}, {character['path']})"
            )
            for character in characters
        ]

        await interaction.response.send_message(
            "**Tracked Characters**\n" + "\n".join(lines),
            ephemeral=True
        )

    @app_commands.command(name="list_roles", description="List character role mappings")
    @app_commands.default_permissions(administrator=True)
    async def list_roles(

        self,

        interaction:
        discord.Interaction

    ):

        role_configs=await get_character_roles(
            interaction.guild.id
        )
        requirement_configs=await get_character_role_requirements(
            interaction.guild.id
        )
        custom_role_configs=await get_custom_roles(
            interaction.guild.id
        )

        if not role_configs and not requirement_configs and not custom_role_configs:
            await interaction.response.send_message(
                "No character roles configured.",
                ephemeral=True
            )
            return

        grouped={}

        for config in role_configs:
            grouped.setdefault(
                config["character_name"],
                []
            ).append(config)

        sections=[]

        if grouped:
            sections.append("**Legacy Role Mappings**")

            for character_name in sorted(grouped):
                lines=[f"**{character_name}**"]

                for config in sorted(
                    grouped[character_name],
                    key=lambda item: item["role_type"]
                ):
                    role=interaction.guild.get_role(
                        config["role_id"]
                    )

                    role_text=(
                        role.mention
                        if role
                        else f"Missing role `{config['role_id']}`"
                    )

                    lines.append(
                        f"{config['role_type']} -> {role_text}"
                    )

                sections.append(
                    "\n".join(lines)
                )

        if requirement_configs:
            sections.append("**Requirement Role Mappings**")

            for config in sorted(
                requirement_configs,
                key=lambda item: (item["character_name"], item["role_id"])
            ):
                role=interaction.guild.get_role(
                    config["role_id"]
                )

                role_text=(
                    role.mention
                    if role
                    else f"Missing role `{config['role_id']}`"
                )

                requirements=[]

                if config["required_eidolons"] > 0:
                    requirements.append(
                        f"- E{config['required_eidolons']}+"
                    )

                if config["required_superimpose"] > 0:
                    requirements.append(
                        f"- S{config['required_superimpose']}+"
                    )

                if config["require_signature"]:
                    requirements.append(
                        "- Signature LC"
                    )

                if config["require_max_traces"]:
                    requirements.append(
                        "- Max Traces"
                    )

                if not requirements:
                    requirements.append(
                        "- Character ownership"
                    )

                sections.append(
                    f"**{config['character_name']}**\n"
                    f"Role:\n"
                    f"{role_text}\n\n"
                    f"Requirements:\n"
                    + "\n".join(requirements)
                )

        if custom_role_configs:
            sections.append("**Custom Date Roles**")

            for config in sorted(
                custom_role_configs,
                key=lambda item: (item["character_name"], item["role_id"])
            ):
                role=interaction.guild.get_role(
                    config["role_id"]
                )

                role_text=(
                    role.mention
                    if role
                    else f"Missing role `{config['role_id']}`"
                )

                sections.append(
                    f"**{config['character_name']}**\n"
                    f"{role_text} -> "
                    f"{config['start_date']} to {config['end_date']} "
                    f"({config['source_type']})"
                )

        await interaction.response.send_message(
            "\n\n".join(sections),
            ephemeral=True
        )

    @app_commands.command(
        name="dev_sync",
        description="Force rebuild all application commands"
    )
    async def force_sync(self, interaction: discord.Interaction):

        # Replace with your Discord User ID
        if interaction.user.id != __main__.OWNER_ID:
            await interaction.response.send_message(
                "❌ You cannot use this command.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        guild = discord.Object(id=__main__.TEST_GUILD_ID)

        # Remove guild commands
        self.bot.tree.clear_commands(guild=guild)
        await self.bot.tree.sync(guild=guild)

        # Remove global commands
        self.bot.tree.clear_commands(guild=None)
        await self.bot.tree.sync()

        # Recreate them
        self.bot.tree.copy_global_to(guild=guild)

        guild_synced = await self.bot.tree.sync(guild=guild)
        global_synced = await self.bot.tree.sync()

        await interaction.followup.send(
            f"✅ Commands rebuilt.\n"
            f"Guild: {len(guild_synced)}\n"
            f"Global: {len(global_synced)}",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Admin(bot))
