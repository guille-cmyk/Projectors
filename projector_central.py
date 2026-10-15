"""
ProjectorCentral Integration for Blender Projector Addon.
Handles downloading, parsing, caching, and querying projector specifications.
"""

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("projector_central")

# Pre-populated library of popular projectors across top brands
DEFAULT_PROJECTOR_DB: Dict[str, Dict[str, Any]] = {
    "benq-ht2050a": {
        "id": "benq-ht2050a",
        "brand": "BenQ",
        "model": "HT2050A",
        "title": "BenQ HT2050A DLP Projector",
        "lumens": 2200,
        "resolution": "1920x1080",
        "res_x": 1920,
        "res_y": 1080,
        "aspect_ratio": "16:9",
        "throw_ratio_min": 1.15,
        "throw_ratio_max": 1.50,
        "throw_ratio_default": 1.325,
        "throw_dist_min_m": 1.34,
        "throw_dist_max_m": 7.65,
        "lens_shift_v": 10.0,
        "lens_shift_h": 0.0,
        "chassis_width": 0.380,
        "chassis_height": 0.121,
        "chassis_depth": 0.277,
        "lens_offset_x": 0.085,
        "display_type": "DLP",
        "contrast": "15,000:1",
        "power_watts": 353,
        "url": "https://www.projectorcentral.com/benq-ht2050a.htm",
    },
    "benq-tk700sti": {
        "id": "benq-tk700sti",
        "brand": "BenQ",
        "model": "TK700STi",
        "title": "BenQ TK700STi 4K Gaming Projector",
        "lumens": 3000,
        "resolution": "3840x2160",
        "res_x": 3840,
        "res_y": 2160,
        "aspect_ratio": "16:9",
        "throw_ratio_min": 0.90,
        "throw_ratio_max": 1.08,
        "throw_ratio_default": 0.99,
        "throw_dist_min_m": 0.91,
        "throw_dist_max_m": 4.78,
        "lens_shift_v": 0.0,
        "lens_shift_h": 0.0,
        "chassis_width": 0.312,
        "chassis_height": 0.110,
        "chassis_depth": 0.246,
        "lens_offset_x": 0.075,
        "display_type": "DLP",
        "contrast": "10,000:1",
        "power_watts": 385,
        "url": "https://www.projectorcentral.com/benq-tk700sti.htm",
    },
    "benq-lk936st": {
        "id": "benq-lk936st",
        "brand": "BenQ",
        "model": "LK936ST",
        "title": "BenQ LK936ST Laser Golf Simulator Projector",
        "lumens": 5100,
        "resolution": "3840x2160",
        "res_x": 3840,
        "res_y": 2160,
        "aspect_ratio": "16:9",
        "throw_ratio_min": 0.81,
        "throw_ratio_max": 0.89,
        "throw_ratio_default": 0.85,
        "throw_dist_min_m": 1.80,
        "throw_dist_max_m": 5.90,
        "lens_shift_v": 60.0,
        "lens_shift_h": 23.0,
        "chassis_width": 0.416,
        "chassis_height": 0.166,
        "chassis_depth": 0.351,
        "lens_offset_x": 0.0,
        "display_type": "DLP (Laser)",
        "contrast": "3,000,000:1",
        "power_watts": 440,
        "url": "https://www.projectorcentral.com/benq-lk936st.htm",
    },
    "epson-home_cinema_5050ub": {
        "id": "epson-home_cinema_5050ub",
        "brand": "Epson",
        "model": "Home Cinema 5050UB",
        "title": "Epson Home Cinema 5050UB 3LCD Projector",
        "lumens": 2600,
        "resolution": "1920x1080",
        "res_x": 1920,
        "res_y": 1080,
        "aspect_ratio": "16:9",
        "throw_ratio_min": 1.35,
        "throw_ratio_max": 2.84,
        "throw_ratio_default": 2.095,
        "throw_dist_min_m": 3.14,
        "throw_dist_max_m": 8.96,
        "lens_shift_v": 96.3,
        "lens_shift_h": 47.1,
        "chassis_width": 0.520,
        "chassis_height": 0.193,
        "chassis_depth": 0.450,
        "lens_offset_x": 0.0,
        "display_type": "3LCD",
        "contrast": "1,000,000:1",
        "power_watts": 373,
        "url": "https://www.projectorcentral.com/Epson-Home_Cinema_5050UB.htm",
    },
    "epson-eb-pu2220b": {
        "id": "epson-eb-pu2220b",
        "brand": "Epson",
        "model": "EB-PU2220B",
        "title": "Epson EB-PU2220B 20,000-Lumen Laser Projector",
        "lumens": 20000,
        "resolution": "1920x1200",
        "res_x": 1920,
        "res_y": 1200,
        "aspect_ratio": "16:10",
        "throw_ratio_min": 1.57,
        "throw_ratio_max": 2.56,
        "throw_ratio_default": 2.065,
        "throw_dist_min_m": 3.38,
        "throw_dist_max_m": 55.0,
        "lens_shift_v": 60.0,
        "lens_shift_h": 18.0,
        "chassis_width": 0.586,
        "chassis_height": 0.218,
        "chassis_depth": 0.492,
        "lens_offset_x": 0.0,
        "display_type": "3LCD (Laser)",
        "contrast": "2,500,000:1",
        "power_watts": 1301,
        "url": "https://www.projectorcentral.com/epson-eb-pu2220b.htm",
    },
    "optoma-uhd50x": {
        "id": "optoma-uhd50x",
        "brand": "Optoma",
        "model": "UHD50X",
        "title": "Optoma UHD50X 240Hz 4K UHD Projector",
        "lumens": 3400,
        "resolution": "3840x2160",
        "res_x": 3840,
        "res_y": 2160,
        "aspect_ratio": "16:9",
        "throw_ratio_min": 1.21,
        "throw_ratio_max": 1.59,
        "throw_ratio_default": 1.40,
        "throw_dist_min_m": 1.20,
        "throw_dist_max_m": 9.90,
        "lens_shift_v": 10.0,
        "lens_shift_h": 0.0,
        "chassis_width": 0.315,
        "chassis_height": 0.118,
        "chassis_depth": 0.270,
        "lens_offset_x": 0.070,
        "display_type": "DLP",
        "contrast": "500,000:1",
        "power_watts": 315,
        "url": "https://www.projectorcentral.com/optoma-uhd50x.htm",
    },
    "optoma-gt1080hdr": {
        "id": "optoma-gt1080hdr",
        "brand": "Optoma",
        "model": "GT1080HDR",
        "title": "Optoma GT1080HDR Short Throw Gaming Projector",
        "lumens": 3800,
        "resolution": "1920x1080",
        "res_x": 1920,
        "res_y": 1080,
        "aspect_ratio": "16:9",
        "throw_ratio_min": 0.50,
        "throw_ratio_max": 0.50,
        "throw_ratio_default": 0.50,
        "throw_dist_min_m": 0.45,
        "throw_dist_max_m": 3.35,
        "lens_shift_v": 0.0,
        "lens_shift_h": 0.0,
        "chassis_width": 0.315,
        "chassis_height": 0.118,
        "chassis_depth": 0.244,
        "lens_offset_x": 0.070,
        "display_type": "DLP",
        "contrast": "50,000:1",
        "power_watts": 325,
        "url": "https://www.projectorcentral.com/optoma-gt1080hdr.htm",
    },
    "panasonic-pt-mz880": {
        "id": "panasonic-pt-mz880",
        "brand": "Panasonic",
        "model": "PT-MZ880",
        "title": "Panasonic PT-MZ880 3LCD Laser Projector",
        "lumens": 8000,
        "resolution": "1920x1200",
        "res_x": 1920,
        "res_y": 1200,
        "aspect_ratio": "16:10",
        "throw_ratio_min": 1.61,
        "throw_ratio_max": 2.76,
        "throw_ratio_default": 2.185,
        "throw_dist_min_m": 1.36,
        "throw_dist_max_m": 29.5,
        "lens_shift_v": 67.0,
        "lens_shift_h": 35.0,
        "chassis_width": 0.561,
        "chassis_height": 0.190,
        "chassis_depth": 0.437,
        "lens_offset_x": 0.0,
        "display_type": "3LCD (Laser)",
        "contrast": "3,000,000:1",
        "power_watts": 490,
        "url": "https://www.projectorcentral.com/panasonic-pt-mz880.htm",
    },
    "panasonic-pt-rq25k": {
        "id": "panasonic-pt-rq25k",
        "brand": "Panasonic",
        "model": "PT-RQ25K",
        "title": "Panasonic PT-RQ25K 3-Chip DLP 4K+ Projector",
        "lumens": 20000,
        "resolution": "3840x2400",
        "res_x": 3840,
        "res_y": 2400,
        "aspect_ratio": "16:10",
        "throw_ratio_min": 1.30,
        "throw_ratio_max": 1.70,
        "throw_ratio_default": 1.50,
        "throw_dist_min_m": 2.0,
        "throw_dist_max_m": 45.0,
        "lens_shift_v": 66.0,
        "lens_shift_h": 28.0,
        "chassis_width": 0.598,
        "chassis_height": 0.300,
        "chassis_depth": 0.640,
        "lens_offset_x": 0.0,
        "display_type": "3-Chip DLP (Laser)",
        "contrast": "25,000:1",
        "power_watts": 1450,
        "url": "https://www.projectorcentral.com/panasonic-pt-rq25k.htm",
    },
    "sony-vpl-xw5000es": {
        "id": "sony-vpl-xw5000es",
        "brand": "Sony",
        "model": "VPL-XW5000ES",
        "title": "Sony VPL-XW5000ES Native 4K SXRD Laser Projector",
        "lumens": 2000,
        "resolution": "3840x2160",
        "res_x": 3840,
        "res_y": 2160,
        "aspect_ratio": "16:9",
        "throw_ratio_min": 1.38,
        "throw_ratio_max": 2.21,
        "throw_ratio_default": 1.795,
        "throw_dist_min_m": 3.05,
        "throw_dist_max_m": 7.35,
        "lens_shift_v": 71.0,
        "lens_shift_h": 25.0,
        "chassis_width": 0.460,
        "chassis_height": 0.200,
        "chassis_depth": 0.472,
        "lens_offset_x": 0.0,
        "display_type": "SXRD / LCoS (Laser)",
        "contrast": "Infinity:1",
        "power_watts": 295,
        "url": "https://www.projectorcentral.com/sony-vpl-xw5000es.htm",
    },
    "barco-balder": {
        "id": "barco-balder",
        "brand": "Barco",
        "model": "Balder",
        "title": "Barco Residential Balder 4K UHD Laser Projector",
        "lumens": 5000,
        "resolution": "3840x2160",
        "res_x": 3840,
        "res_y": 2160,
        "aspect_ratio": "16:9",
        "throw_ratio_min": 1.25,
        "throw_ratio_max": 1.60,
        "throw_ratio_default": 1.425,
        "throw_dist_min_m": 2.50,
        "throw_dist_max_m": 20.0,
        "lens_shift_v": 60.0,
        "lens_shift_h": 30.0,
        "chassis_width": 0.475,
        "chassis_height": 0.223,
        "chassis_depth": 0.593,
        "lens_offset_x": 0.0,
        "display_type": "DLP (Laser)",
        "contrast": "10,000:1",
        "power_watts": 570,
        "url": "https://www.projectorcentral.com/barco-balder.htm",
    },
    "christie-m-4k25-rgb": {
        "id": "christie-m-4k25-rgb",
        "brand": "Christie",
        "model": "M 4K25 RGB",
        "title": "Christie M 4K25 RGB Pure Laser Projector",
        "lumens": 25000,
        "resolution": "3840x2160",
        "res_x": 3840,
        "res_y": 2160,
        "aspect_ratio": "16:9",
        "throw_ratio_min": 1.20,
        "throw_ratio_max": 1.80,
        "throw_ratio_default": 1.50,
        "throw_dist_min_m": 2.5,
        "throw_dist_max_m": 60.0,
        "lens_shift_v": 100.0,
        "lens_shift_h": 40.0,
        "chassis_width": 0.676,
        "chassis_height": 0.356,
        "chassis_depth": 0.597,
        "lens_offset_x": 0.0,
        "display_type": "3-Chip DLP (RGB Laser)",
        "contrast": "27,000:1",
        "power_watts": 1900,
        "url": "https://www.projectorcentral.com/christie-m-4k25-rgb.htm",
    },
    "viewsonic-px701-4k": {
        "id": "viewsonic-px701-4k",
        "brand": "ViewSonic",
        "model": "PX701-4K",
        "title": "ViewSonic PX701-4K 3200-Lumen 4K Projector",
        "lumens": 3200,
        "resolution": "3840x2160",
        "res_x": 3840,
        "res_y": 2160,
        "aspect_ratio": "16:9",
        "throw_ratio_min": 1.50,
        "throw_ratio_max": 1.65,
        "throw_ratio_default": 1.575,
        "throw_dist_min_m": 1.0,
        "throw_dist_max_m": 10.96,
        "lens_shift_v": 0.0,
        "lens_shift_h": 0.0,
        "chassis_width": 0.312,
        "chassis_height": 0.108,
        "chassis_depth": 0.222,
        "lens_offset_x": 0.065,
        "display_type": "DLP",
        "contrast": "12,000:1",
        "power_watts": 310,
        "url": "https://www.projectorcentral.com/viewsonic-px701-4k.htm",
    },
}


def get_db_file_path() -> Path:
    """Return the local path for storing cached projector specs."""
    base_dir = Path(__file__).resolve().parent
    return base_dir / "projector_models_db.json"


def load_projectors_db() -> Dict[str, Dict[str, Any]]:
    """Load projector database from disk, merging with built-in defaults."""
    db = dict(DEFAULT_PROJECTOR_DB)
    db_file = get_db_file_path()
    if db_file.exists():
        try:
            with open(db_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    db.update(saved)
        except Exception as e:
            log.warning(f"Could not load custom projector database: {e}")
    return db


def save_projector_to_db(model_data: Dict[str, Any]) -> None:
    """Save a newly downloaded or updated model to the persistent JSON database."""
    model_id = model_data.get("id")
    if not model_id:
        return
    current_db = load_projectors_db()
    current_db[model_id] = model_data

    # Save to disk
    db_file = get_db_file_path()
    try:
        with open(db_file, "w", encoding="utf-8") as f:
            json.dump(current_db, f, indent=2)
    except Exception as e:
        log.error(f"Failed to persist projector database to {db_file}: {e}")


def get_brands() -> List[str]:
    """Return a sorted list of unique brands in the database."""
    db = load_projectors_db()
    brands = set(data.get("brand", "Unknown") for data in db.values())
    return sorted(list(brands))


def get_models_for_brand(brand: str) -> List[Tuple[str, str, str]]:
    """Return models belonging to a specific brand formatted for Blender EnumProperty items."""
    db = load_projectors_db()
    items = []
    idx = 1
    for model_id, data in sorted(db.items(), key=lambda x: x[1].get("model", "")):
        if data.get("brand", "").lower() == brand.lower():
            label = f"{data.get('model', model_id)} ({data.get('lumens', '?')} lm, {data.get('resolution', '')})"
            desc = f"{data.get('title', '')} - Throw Ratio: {data.get('throw_ratio_min', '')}-{data.get('throw_ratio_max', '')}"
            items.append((model_id, label, desc, idx))
            idx += 1
    return items


def fetch_projector_specs(model_or_url: str) -> Dict[str, Any]:
    """
    Download and parse projector specs directly from ProjectorCentral.com.
    Accepts a model slug (e.g. 'benq-ht2050a' or 'BenQ HT2050A') or a full URL.
    """
    model_str = model_or_url.strip()
    if model_str.startswith("http://") or model_str.startswith("https://"):
        url = model_str
    else:
        # Normalize slug
        slug = model_str.replace(" ", "_")
        if not slug.lower().endswith(".htm"):
            slug += ".htm"
        url = f"https://www.projectorcentral.com/{slug}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            html = response.read().decode("utf-8", errors="ignore")
            final_url = response.geturl()
    except Exception as e:
        # If uppercase underscore failed with 404, try lowercase hyphen
        if "404" in str(e) and "_" in url:
            alt_url = url.lower().replace("_", "-")
            req_alt = urllib.request.Request(alt_url, headers=req.headers)
            try:
                with urllib.request.urlopen(req_alt, timeout=12) as response:
                    html = response.read().decode("utf-8", errors="ignore")
                    final_url = response.geturl()
            except Exception as e2:
                raise RuntimeError(f"Failed to fetch from ProjectorCentral: {e2}")
        else:
            raise RuntimeError(f"Failed to fetch from ProjectorCentral: {e}")

    return parse_projectorcentral_html(html, final_url)


def parse_projectorcentral_html(html: str, url: str) -> Dict[str, Any]:
    """Parse HTML from a ProjectorCentral model page into structured specifications."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
    except ImportError:
        # Fallback to regex parser if bs4 is missing
        soup = None

    raw_specs: Dict[str, str] = {}
    title = ""

    if soup:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

        for dl in soup.find_all("dl"):
            dd = dl.find("dd")
            dt = dl.find("dt")
            if dd and dt:
                label = dd.get_text(strip=True)
                val = dt.get_text(strip=True)
                raw_specs[label] = val
    else:
        # Simple regex fallback
        m_title = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        if m_title:
            title = re.sub(r"<[^>]+>", "", m_title.group(1)).strip()

        dl_matches = re.findall(
            r"<dl[^>]*>\s*<dd[^>]*>(.*?)</dd>\s*<dt[^>]*>(.*?)</dt>\s*</dl>",
            html,
            re.I | re.S,
        )
        for dd_raw, dt_raw in dl_matches:
            k = re.sub(r"<[^>]+>", "", dd_raw).strip()
            v = re.sub(r"<[^>]+>", "", dt_raw).strip()
            raw_specs[k] = v

    # Derive model ID, brand, model
    url_path = urllib.parse.urlparse(url).path
    filename = Path(url_path).stem
    model_id = filename.lower().replace("_", "-")

    parts = filename.replace("_", " ").replace("-", " ").split()
    brand = parts[0].capitalize() if parts else "Unknown"
    model = " ".join(parts[1:]) if len(parts) > 1 else filename

    data: Dict[str, Any] = {
        "id": model_id,
        "brand": brand,
        "model": model,
        "title": title or f"{brand} {model}",
        "url": url,
        "lumens": 2000,
        "resolution": "1920x1080",
        "res_x": 1920,
        "res_y": 1080,
        "aspect_ratio": "16:9",
        "throw_ratio_min": 1.2,
        "throw_ratio_max": 1.5,
        "throw_ratio_default": 1.35,
        "throw_dist_min_m": 1.5,
        "throw_dist_max_m": 8.0,
        "lens_shift_v": 0.0,
        "lens_shift_h": 0.0,
        "chassis_width": 0.380,
        "chassis_height": 0.121,
        "chassis_depth": 0.277,
        "lens_offset_x": 0.0,
        "display_type": "DLP",
        "contrast": "",
        "power_watts": 300,
    }

    # 1. Lumens / Brightness
    for k in ["Brightness", "White Brightness", "Color Brightness"]:
        if k in raw_specs:
            m = re.search(r"([\d,]+)\s*Lumens", raw_specs[k], re.I)
            if m:
                data["lumens"] = int(m.group(1).replace(",", ""))
                break

    # 2. Resolution & Aspect Ratio
    if "Resolution" in raw_specs:
        m = re.search(r"(\d{3,4})\s*x\s*(\d{3,4})", raw_specs["Resolution"])
        if m:
            rx, ry = int(m.group(1)), int(m.group(2))
            data["res_x"] = rx
            data["res_y"] = ry
            data["resolution"] = f"{rx}x{ry}"

    if "Aspect Ratio" in raw_specs:
        data["aspect_ratio"] = raw_specs["Aspect Ratio"].split()[0]
    elif data["res_x"] and data["res_y"]:
        gcd_val = _gcd(data["res_x"], data["res_y"])
        data["aspect_ratio"] = f"{data['res_x']//gcd_val}:{data['res_y']//gcd_val}"

    # 3. Throw Ratio
    if "Throw Ratio" in raw_specs:
        tr_str = raw_specs["Throw Ratio"]
        matches = re.findall(r"(\d+\.?\d*)\s*:\s*1", tr_str)
        if matches:
            t_min = float(matches[0])
            t_max = float(matches[-1])
            data["throw_ratio_min"] = t_min
            data["throw_ratio_max"] = t_max
            data["throw_ratio_default"] = round((t_min + t_max) / 2.0, 3)

    # 4. Throw Distance (convert feet to meters if needed)
    if "Throw Distance" in raw_specs:
        td_str = raw_specs["Throw Distance"]
        feet_matches = re.findall(r"(\d+\.?\d*)'", td_str)
        if feet_matches:
            data["throw_dist_min_m"] = round(float(feet_matches[0]) * 0.3048, 2)
            data["throw_dist_max_m"] = round(float(feet_matches[-1]) * 0.3048, 2)
        else:
            m_matches = re.findall(r"(\d+\.?\d*)\s*m", td_str, re.I)
            if m_matches:
                data["throw_dist_min_m"] = float(m_matches[0])
                data["throw_dist_max_m"] = float(m_matches[-1])

    # 5. Lens Shift
    if "Lens Shift" in raw_specs:
        ls_str = raw_specs["Lens Shift"]
        v_match = re.search(r"Vertical\s*([+\-/0-9.%]+)", ls_str, re.I)
        h_match = re.search(r"Horizontal\s*([+\-/0-9.%]+)", ls_str, re.I)
        if v_match:
            num = re.search(r"(\d+\.?\d*)", v_match.group(1))
            if num:
                data["lens_shift_v"] = float(num.group(1))
        if h_match:
            num = re.search(r"(\d+\.?\d*)", h_match.group(1))
            if num:
                data["lens_shift_h"] = float(num.group(1))

    # 6. Technology & Contrast & Power
    if "Display Type" in raw_specs:
        data["display_type"] = raw_specs["Display Type"]
    if "Dynamic Contrast" in raw_specs:
        data["contrast"] = raw_specs["Dynamic Contrast"]
    elif "Contrast" in raw_specs:
        data["contrast"] = raw_specs["Contrast"]
    if "Power" in raw_specs:
        m_pow = re.search(r"(\d+)\s*Watts", raw_specs["Power"], re.I)
        if m_pow:
            data["power_watts"] = int(m_pow.group(1))

    # 7. Physical Dimensions (Height x Width x Depth)
    for k in ["Dimensions", "Size", "Product Dimensions"]:
        if k in raw_specs:
            dim_str = raw_specs[k]
            m_in = re.findall(r'(\d+\.?\d*)\s*["\']', dim_str)
            if len(m_in) >= 3:
                data["chassis_height"] = round(float(m_in[0]) * 0.0254, 3)
                data["chassis_width"] = round(float(m_in[1]) * 0.0254, 3)
                data["chassis_depth"] = round(float(m_in[2]) * 0.0254, 3)
                break
            m_cm = re.findall(r'(\d+\.?\d*)\s*cm', dim_str, re.I)
            if len(m_cm) >= 3:
                data["chassis_height"] = round(float(m_cm[0]) * 0.01, 3)
                data["chassis_width"] = round(float(m_cm[1]) * 0.01, 3)
                data["chassis_depth"] = round(float(m_cm[2]) * 0.01, 3)
                break

    return data


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a
