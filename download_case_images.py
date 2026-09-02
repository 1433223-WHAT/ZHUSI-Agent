"""Download images for 4 flagship cases from ArchDaily."""
import sys, time, re
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# URL lists from fetch_archdaily_images.py output
CASE_IMAGES = {
    "Villa_Savoye": [
        "https://images.adsttc.com/media/images/5037/e694/28ba/0d59/9b00/035d/large_jpg/stringio.jpg",
        "https://images.adsttc.com/media/images/5037/e6a9/28ba/0d59/9b00/0361/large_jpg/stringio.jpg",
        "https://images.adsttc.com/media/images/5037/e6a3/28ba/0d59/9b00/0360/large_jpg/stringio.jpg",
        # Last = drawings
        "https://images.adsttc.com/media/images/5037/e6db/28ba/0d59/9b00/036d/large_jpg/stringio.jpg",
    ],
    "Kimbell_Art_Museum": [
        "https://images.adsttc.com/media/images/5038/0892/28ba/0d59/9b00/0a3a/large_jpg/stringio.jpg",
        "https://images.adsttc.com/media/images/5038/08af/28ba/0d59/9b00/0a43/large_jpg/stringio.jpg",
        "https://images.adsttc.com/media/images/5038/088f/28ba/0d59/9b00/0a39/large_jpg/stringio.jpg",
        # Archigraphie = plans/sections drawings
        "https://images.adsttc.com/media/images/5273/7dfc/e8e4/4ee8/e100/0800/large_jpg/©_Archigraphie_1.jpg",
    ],
    "Barcelona_Pavilion": [
        "https://images.adsttc.com/media/images/54c6/a195/e58e/ced6/7000/0007/large_jpg/Mies4.jpg",
        "https://images.adsttc.com/media/images/5037/fe3d/28ba/0d59/9b00/07e3/large_jpg/stringio.jpg",
        "https://images.adsttc.com/media/images/54c6/a744/e58e/ceb2/c700/0001/large_jpg/Mies2.jpg",
        # Last = drawings
        "https://images.adsttc.com/media/images/5037/febe/28ba/0d59/9b00/07f4/large_jpg/stringio.jpg",
    ],
    "Therme_Vals": [
        "https://images.adsttc.com/media/images/5fc1/4189/63c0/17d6/2c00/122a/large_jpg/09102014-ACP_Therme_Vals_2014.10_8627-2.jpg",
        "https://images.adsttc.com/media/images/500f/244f/28ba/0d0c/c700/1d3c/large_jpg/stringio.jpg",
        "https://images.adsttc.com/media/images/500f/2452/28ba/0d0c/c700/1d3d/large_jpg/stringio.jpg",
        # Plan/section (older ArchDaily set)
        "https://images.adsttc.com/media/images/500f/2469/28ba/0d0c/c700/1d42/large_jpg/stringio.jpg",
    ],
}

BASE = Path(__file__).resolve().parent / "images"

for case, urls in CASE_IMAGES.items():
    case_dir = BASE / case
    case_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {case} ===")
    for i, url in enumerate(urls):
        # Name: plan.jpg for last, space_XX.jpg for photos
        if i == len(urls) - 1:
            fname = "plan.jpg"
        else:
            fname = f"space_0{i+1}.jpg"
        path = case_dir / fname
        if path.exists():
            print(f"  [EXISTS] {fname}")
            continue
        print(f"  Downloading {fname} <- {url[:70]}...")
        try:
            r = requests.get(url, headers=H, timeout=30, stream=True)
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            print(f"    OK: {path.stat().st_size} bytes")
        except Exception as e:
            print(f"    FAIL: {e}")
        time.sleep(1)

print("\n=== Summary ===")
for case in CASE_IMAGES:
    case_dir = BASE / case
    files = sorted(case_dir.glob("*.jpg"))
    print(f"  {case}: {len(files)} files")
    for f in files:
        print(f"    {f.name}: {f.stat().st_size//1024} KB")
