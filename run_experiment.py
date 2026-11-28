"""
Experiment script for eye tracking experiment.

Presents images one by one (5 s) with fixation crosses in between
(3 s, left or right). Participant ID first, then instructions.
Logs trial order and image type (color or grayscale).
"""
import random
import tkinter as tk
from pathlib import Path
import pandas as pd
import hengam
from PIL import Image, ImageTk

root = tk.Tk()
root.attributes("-fullscreen", True)
root.update_idletasks()
SCREEN_WIDTH = root.winfo_screenwidth()
SCREEN_HEIGHT = root.winfo_screenheight()

IMG_MS = 5000             # image duration
FIX_MS = 3000             # fixation duration
BG_COLOR = "#808080"
FIX_COLOR = "#4d4d4d"
CENTER_MARGIN = 40

OUTPUT_FILE_TEMPLATE = "experiment_log__{participant}_{condition}.csv"
STIM_FOLDERS = {"color": "color", "gray": "grayscale"}

OUTPUT_DIR = Path("results")
OUTPUT_DIR.mkdir(exist_ok=True)

tracker = None
all_samples = []

def show_text(canvas, lines, size=18, spacing=60):
    """Display instruction text centrally."""
    y = SCREEN_HEIGHT / 2 - (len(lines) - 1) * spacing / 2
    for line in lines:
        canvas.create_text(SCREEN_WIDTH / 2, y, text=line, fill="white", font=("Helvetica", size))
        y += spacing

def ask_participant(canvas):
    """Ask for the participant number, return it via Enter."""
    show_text(canvas, ["Participant number:"], size=24, spacing=0)
    entry = tk.Entry(font=("Helvetica", 20), justify="center")
    entry.focus_set()
    canvas.create_window(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 60, window=entry)

    def on_enter(event):
        participant = entry.get()
        entry.destroy()
        show_instructions(canvas, participant)
    entry.bind("<Return>", on_enter)

def show_instructions(canvas, participant):
    """Explain the task, start the experiment on SPACE."""
    canvas.delete("all")
    show_text(canvas, [
        "Welcome!",
        "You will see a series of images. Each image appears for a brief period of time.",
        "Look for the marker hidden in every image.",
        "Between images, a fixation cross will appear on the left or right side.",
        "Please fixate the cross when shown.",
        "",
        "Press SPACE to begin.",
    ], size=20)
    root.bind("<space>", lambda e: run_trials(canvas, participant))

def make_order(condition):
    """All images of one condition, shuffled: a participant sees only that version."""
    paths = sorted(Path(STIM_FOLDERS[condition]).glob("*.png"))
    order = [(path, condition) for path in paths]
    random.shuffle(order)
    return order

def run_trials(canvas, participant):
    """Alternate fixation and image screens until all images are shown."""
    condition = random.choice(("color", "gray"))
    order = make_order(condition)
    state = {"i": 0, "participant": participant, "condition": condition}
    log = []
    show_fixation(canvas, lambda: show_image(canvas, order, state, log))

def show_fixation(canvas, next_fn):
    """Draw a fixation cross on one side of the screen."""
    canvas.delete("all")
    side = random.choice(("left", "right"))
    cx = SCREEN_WIDTH * (0.25 if side == "left" else 0.75)
    cy = SCREEN_HEIGHT / 2
    canvas.create_line(cx - 20, cy, cx + 20, cy, fill=FIX_COLOR, width=3)
    canvas.create_line(cx, cy - 20, cx, cy + 20, fill=FIX_COLOR, width=3)
    root.after(FIX_MS, next_fn)

def show_image(canvas, order, state, log):
    """Show one centered image for IMG_MS."""
    global photo, tracker, all_samples
    canvas.delete("all")
    if state["i"] >= len(order):
        save_log(log, state)
        save_gaze_data(state)
        show_done(canvas)
        return
    path, _ = order[state["i"]]
    image_name = path.stem
    photo = ImageTk.PhotoImage(Image.open(path).convert("RGB"))
    item = canvas.create_image(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, anchor="center", image=photo)
    x, y = canvas.coords(item)
    w, h = photo.width(), photo.height()
    log.append({"order": state["i"] + 1, "theme": path.stem,
                "img_x_px": x - w / 2, "img_y_px": y - h / 2,
                "disp_w": w, "disp_h": h})

    # Start gaze recording when image appears
    tracker.clear()
    tracker.start_recording()
    
    state["i"] += 1
    root.after(IMG_MS, lambda: finish_image(canvas, order, state, log, image_name))

def finish_image(canvas, order, state, log, image_name):
    """Stop recording and collect gaze samples after image disappears."""
    global tracker, all_samples

    tracker.stop_recording()

    samples = pd.DataFrame(tracker.get_samples())
    samples["image"] = image_name
    all_samples.append(samples)

    show_fixation(canvas, lambda: show_image(canvas, order, state, log))

def save_gaze_data(state):
    """Save all gaze samples to a CSV named by participant."""
    global all_samples

    df = pd.concat(all_samples, ignore_index=True)
    output_file = OUTPUT_DIR / (f"gaze_data_{state['participant']}.csv")
    df.to_csv(output_file, index=False)

    print(f"Gaze data saved to: {output_file}")

def save_log(log, state):
    """Write the trial log to a CSV named by participant and condition."""
    output_file = OUTPUT_DIR / OUTPUT_FILE_TEMPLATE.format(participant=state["participant"], condition=state["condition"])
    
    pd.DataFrame(log).to_csv(output_file, index=False)

def show_done(canvas):
    """Thank-you screen, then close."""
    canvas.delete("all")
    show_text(canvas, ["Done. Thank you!"], size=28, spacing=0)
    root.after(3000, root.destroy)

def main():
    global tracker

    root.configure(bg=BG_COLOR, cursor="none")
    canvas = tk.Canvas(root, bg=BG_COLOR, highlightthickness=0, cursor="none")
    canvas.pack(fill="both", expand=True)
    root.bind("<Escape>", lambda e: root.destroy())
    root.focus_set()

    with hengam.EyeTracker(SCREEN_WIDTH, SCREEN_HEIGHT) as eye_tracker:
        tracker = eye_tracker

        ask_participant(canvas)
        root.mainloop()

if __name__ == "__main__":
    main()