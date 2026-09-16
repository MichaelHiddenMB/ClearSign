"""Downloads the real-photo benchmark images listed in real/manifest.json from Wikimedia Commons.

The images are Creative Commons licensed (see manifest.json for author and licence)
and are not committed to the repository.
"""

from __future__ import annotations

import io
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent / "real"
UA = {"User-Agent": "ClearSignBench/0.1 (accessibility OCR benchmark)"}


def commons_url(title: str, width: int = 1600) -> str:
    query = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "imageinfo", "iiprop": "url",
                                    "iiurlwidth": width, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + query, headers=UA)) as r:
        page = next(iter(json.load(r)["query"]["pages"].values()))
    info = page["imageinfo"][0]
    return info.get("thumburl") or info["url"]


def main() -> None:
    manifest = json.loads((HERE / "manifest.json").read_text())
    for entry in manifest:
        target = HERE / entry["file"]
        if target.exists():
            continue
        url = commons_url(entry["title"])
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
            image = Image.open(io.BytesIO(r.read())).convert("RGB")
        if entry.get("crop"):
            image = image.crop(tuple(entry["crop"]))
        image.thumbnail((1600, 1600))
        image.save(target, quality=88)
        print("fetched", target.name)
    print("done")


if __name__ == "__main__":
    main()
