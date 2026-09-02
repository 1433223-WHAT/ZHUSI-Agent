"""Fetch image URLs from ArchDaily AD Classics pages for 4 flagship cases."""
import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ARCHDAILY_PAGES = {
    "Villa_Savoye": "https://www.archdaily.com/84524/ad-classics-villa-savoye-le-corbusier",
    "Kimbell_Art_Museum": "https://www.archdaily.com/123761/ad-classics-kimbell-art-museum-louis-kahn",
    "Barcelona_Pavilion": "https://www.archdaily.com/109135/ad-classics-barcelona-pavilion-mies-van-der-rohe",
    "Therme_Vals": "https://www.archdaily.com/13358/the-therme-vals",
}

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

for case, url in ARCHDAILY_PAGES.items():
    print(f"\n=== {case} ===")
    print(f"  URL: {url}")
    try:
        r = requests.get(url, headers=H, timeout=20)
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}")
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        imgs = soup.select(".gallery-thumbs img, .afd-gal-items img, .gallery-item img")
        urls = []
        for img in imgs:
            src = img.get("src", "") or img.get("data-src", "")
            if src:
                large = src.replace("medium_jpg", "large_jpg").split("?")[0]
                if large not in urls:
                    urls.append(large)
        print(f"  Found {len(urls)} images")
        for u in urls:
            print(f"    {u}")
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(1.5)
