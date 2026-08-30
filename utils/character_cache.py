import enka
import asyncio
from enka.hsr import Path
from utils.signature_lc import (get_signature_lc)

HSR_CHARACTER_CACHE={}

async def update_hsr_cache():

    global HSR_CHARACTER_CACHE

    print(
        "Updating HSR character cache..."
    )

    async with enka.HSRClient(
        enka.hsr.Language.ENGLISH
    ) as api:

        await api.update_assets()

        cache = {}

        for character_id, data in api._assets.character_data.items():

            text_map_hash = data["AvatarName"]["Hash"]

            name = api._text_map[text_map_hash]

            display_name = f"{name} (HSR)"

            cache[display_name] = {
                "game": "HSR",
                "name": name,
                "id": int(character_id),

                # "PRESERVATION" -> "Preservation"
                "path": Path(data["AvatarBaseType"]).name.replace("_", " ").title(),

                "signature_lc": get_signature_lc(name),
            }

        HSR_CHARACTER_CACHE = cache

    print(
        f"Loaded {len(cache)} characters"
    )

def get_hsr_character_names():

    return sorted(

        HSR_CHARACTER_CACHE.keys()

    )

def get_hsr_character(name):

    return HSR_CHARACTER_CACHE.get(
        name
    )

def get_required_trace_count(
path
):

    trace_map={

        "Destruction":17,

        "Hunt":17,

        "Erudition":17,

        "Harmony":17,

        "Nihility":17,

        "Preservation":17,

        "Abundance":17,

        "Remembrance":19,

        "Elation":18

    }

    return trace_map.get(
        path,
        17
    )