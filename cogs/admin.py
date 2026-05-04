import discord
from discord.ext import commands
from discord import app_commands
import datetime
import __main__

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
        uid: str
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
            api_result = await __main__.get_character_status(uid_int)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to fetch UID.\n{e}" , ephemeral=True
            )
            return

        member = interaction.user

        log_channel = interaction.guild.get_channel(
            __main__.VERIFY_LOG_CHANNEL_ID
        )

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

        if log_channel:
            await log_channel.send(log_header + msg)

        await interaction.followup.send(
        msg,
        ephemeral=True)

        # =========================
        # OWNER CHECK
        # =========================
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

        if not ownership_ok:

            fail_msg = (
                log_header +
                "⚠️ **Ownership Check Failed**\n"
                f"Discord Name: **{member.display_name}**\n"
                f"Enka Name: **{enka_name}**\n"
                f"Signature: {enka_sig}"
            )

            if log_channel:
                await log_channel.send(fail_msg)

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
        if log_channel:
            await log_channel.send(
                log_header +
                "✅ **Passed Owner Verification**"
            )

        # =========================
        # CHARACTER INFO MESSAGE
        # =========================
        chars = api_result["characters"]

        msg = f"👤Name: **{api_result['nickname']}**\n"
        msg += f"📝Signature: {api_result['signature']}\n"
        msg += f"🆔 UID: **{uid}**\n\n"

        for name in ["Sparkle", "Sparxie"]:
            data = chars.get(name)

            if not data:
                msg += f"**{name}**: ❌ Not Found\n\n"
                continue

            lc = data["light_cone"]

            sig_on = False
            sig_text = "❌ Off"

            if name == "Sparkle" and lc and lc["name"] == "Earthly Escapade":
                sig_on = True
                sig_text = "✅ On"

            if name == "Sparxie" and lc and lc["name"] == "Dazzled by a Flowery World":
                sig_on = True
                sig_text = "✅ On"

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

       

        # =========================
        # ROLE ASSIGNMENT
        # =========================
        async def dual_send(self, content):
            await interaction.followup.send(
                content,
                ephemeral=True
            )

            if log_channel:
                await log_channel.send(content)

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

async def setup(bot):
    await bot.add_cog(Admin(bot))