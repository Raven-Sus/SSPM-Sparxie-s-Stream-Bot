import json


with open(
    "data/hsr_signature_lc.json",
    encoding="utf-8"
) as f:
    SIGNATURE_DATA=json.load(f)["HSR"]


def get_signature_lc(character_name):
    data=SIGNATURE_DATA.get(character_name)

    if not data:
        return None

    signature = data["signature_lightcone"]["name"]
    return signature