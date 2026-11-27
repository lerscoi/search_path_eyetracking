"""
Builds eyetracking stimuli from selected candidate images from OASIS dataset.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image

W, H, BAR, STEM = 15, 20, 2, 3
S = max(W, H)
STEP = 10                      # grid step for candidate windows
EXCLUDE_R = 0.5                # fraction of min(image dims): no marker near center
MARKER_DARKEN = 60             # how much darker than its background the marker is

CANDIDATES_DIR = "candidates"
STIM_DIRS = {"color": "stimuli/color", "gray": "stimuli/gray"}
FINAL_DIRS = {"color": "color", "gray": "gray"}
rng = np.random.default_rng(0)

def select_candidates(oasis_file="oasis.csv", out_file="selected.csv"):
    """Match candidate filenames to oasis.csv rows and save the subset."""
    cands = [p.stem for p in Path(CANDIDATES_DIR).glob("*")]
    oasis = pd.read_csv(oasis_file)
    sub = oasis[oasis["Theme"].isin(cands)]
    sub.to_csv(out_file, index=False)
    return sub["Theme"]

def normalize_contrast(img):
    """Robust contrast normalization: clip to 1st-99th percentiles, rescale to 0-255."""
    lo, hi = np.percentile(img, (1, 99))
    return np.clip((img - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)

def convert_images(names):
    """Save normalized color and Gleam gray versions of every candidate image."""
    for d in STIM_DIRS.values():
        Path(d).mkdir(parents=True, exist_ok=True)
    for name in names:
        img = normalize_contrast(np.asarray(Image.open(f"{CANDIDATES_DIR}/{name}.jpg").convert("RGB")))
        gray = np.asarray(img).mean(axis=2).round().astype(np.uint8)  # Gleam: mean of R'G'B'
        Image.fromarray(img).save(f"{STIM_DIRS['color']}/{name}.png")
        Image.fromarray(gray).save(f"{STIM_DIRS['gray']}/{name}.png")

def letter_mask(letter):
    """Build an S x S marker mask so any np.rot90 rotation still fits the slice."""
    mask = np.zeros((S, S), bool)
    if letter == "T":
        mask[:BAR] = True
        mask[:, (S - STEM) // 2:(S + STEM) // 2] = True
    else:
        mask[:, :STEM] = True
        mask[S - BAR:] = True
    return mask

def entropy_windows(gray):
    """Shannon entropy of pixel intensities for each STEP-aligned S x S window."""
    h, w = gray.shape
    hs = np.arange(0, h - S, STEP)
    ws = np.arange(0, w - S, STEP)
    ent = np.zeros((len(hs), len(ws)))
    for j, y in enumerate(hs):
        for i, x in enumerate(ws):
            counts = np.bincount(gray[y:y + S, x:x + S].ravel(), minlength=256)
            p = counts / counts.sum()
            p = p[p > 0]
            ent[j, i] = -(p * np.log2(p)).sum()
    return hs, ws, ent

def pick_position(gray):
    """Pick a high-entropy window position, excluding the image center."""
    h, w = gray.shape
    r_min = EXCLUDE_R * min(h, w)
    hs, ws, ent = entropy_windows(gray)
    centers_x, centers_y = ws + S / 2, hs + S / 2
    ok = np.hypot(centers_x[None, :] - w / 2, centers_y[:, None] - h / 2) > r_min
    weights = np.where(ok.ravel(), np.log1p(ent.ravel()), 0)
    idx = rng.choice(weights.size, p=weights / weights.sum())
    j, i = divmod(idx, len(ws))
    return int(ws[i]), int(hs[j])

def hide_marker(name, letter, k_rot):
    """Hide the rotated, contrast-matching marker in both image versions; return its placement row."""
    mask = np.rot90(letter_mask(letter), k_rot)
    gray = np.asarray(Image.open(f"{STIM_DIRS['gray']}/{name}.png"))
    h, w = gray.shape
    x, y = pick_position(gray)

    for d, folder in STIM_DIRS.items():
        img = np.asarray(Image.open(f"{folder}/{name}.png")).copy()
        patch = img[y:y + S, x:x + S].astype(float)
        marker_rgb = patch[mask].mean(axis=0)
        marker_val = np.clip(marker_rgb - MARKER_DARKEN, 0, 255).astype(np.uint8)
        img[y:y + S, x:x + S][mask] = marker_val
        Path(FINAL_DIRS[d]).mkdir(parents=True, exist_ok=True)
        Image.fromarray(img).save(f"{FINAL_DIRS[d]}/{name}.png")
    return {"Theme": name, "letter": letter, "rot": k_rot, "x": x, "y": y,
            "img_w": w, "img_h": h, "w": S, "h": S}

def main():
    names = select_candidates()
    convert_images(names)
    targets = []
    for k, name in enumerate(names):
        letter = "TL"[k % 2]
        k_rot = int(rng.integers(0, 4))
        targets.append(hide_marker(name, letter, k_rot))
    pd.DataFrame(targets).to_csv("targets.csv", index=False)

if __name__ == "__main__":
    main()