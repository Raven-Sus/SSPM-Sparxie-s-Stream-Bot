import asyncio
import enka

#-------------------#

Debug = False

#-------------------#

TARGET_CHARACTERS = ["Sparkle", "Sparxie"]
REQUIRED_TRACE_COUNTS = {
    "Sparkle": 17,
    "Sparxie": 18,}

def is_fully_maxed(character):
    for trace in character.traces:
        if trace.level < trace.max_level:
            return False
    return True


def check_traces(character):
    all_good = True
    for trace in character.traces:
        if trace.level < trace.max_level:
            print(f"❌ Not maxed: ID {trace.id} ({trace.level}/{trace.max_level})")
            all_good = False
    return all_good


async def get_character_status(uid):
    async with enka.HSRClient(enka.hsr.Language.ENGLISH) as api:
        await api.update_assets()
        response = await api.fetch_showcase(uid)


        result = {
        "nickname": response.player.nickname,
        "signature": response.player.signature or "No bio",
        "characters": {}
        }

        for name in TARGET_CHARACTERS:
            result["characters"][name] = None

        for character in response.characters:
            if character.name not in TARGET_CHARACTERS:
                continue

            # 🔹 Trace Check
            fully_maxed = True
            issues = []

            required_count = REQUIRED_TRACE_COUNTS.get(character.name, 0)
            current_count = len(character.traces)

            # Check missing locked nodes
            if current_count < required_count:
                fully_maxed = False
                issues.append(
                    f"Locked trace nodes missing ({current_count}/{required_count})"
                )

            # Check unlocked nodes not maxed
            for trace in character.traces:
                if Debug:
                    print(trace)
                if trace.level < trace.max_level:
                    fully_maxed = False

                    label = trace.name.strip() if trace.name else f"ID {trace.id}"

                    issues.append(
                        f"{label} ({trace.level}/{trace.max_level})"
                    )


            # 🔹 Light Cone
            lc = character.light_cone
            lc_info = None
            if lc:
                lc_info = {
                    "name": lc.name,
                    "superimpose": lc.superimpose
                }


            # 🔹 Eidolons
            result["characters"][character.name] ={
                "eidolons": character.eidolons_unlocked,
                "fully_maxed": fully_maxed,
                "issues": issues,
                "light_cone": lc_info
            }
        print(result)
        return result


#asyncio.run(get_character_status(800415467))

#800415467 , 800436487