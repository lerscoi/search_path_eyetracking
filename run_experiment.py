"""
Experiment script for eye tracking experiment.

Presents images one by one (5 s) with fixation crosses in between
(3 s, left or right). Participant ID first, then instructions.
Logs trial order and image type (color or grayscale) and saves the
recorded gaze samples together with the trial they belong to.
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

OUTPUT_FILE_TEMPLATE = "experiment_log_{participant}_{condition}.csv"
GAZE_FILE_TEMPLATE = "gaze_data_{participant}.csv"
STIM_FOLDERS = {"color": "color", "gray": "grayscale"}

OUTPUT_DIR = Path("results")
OUTPUT_DIR.mkdir(exist_ok=True)

tracker = None
all_samples = []
session = None

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
        participant = entry.get().strip()
        if not participant:
            return
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
    global all_samples, session

    root.unbind("<space>")
    condition = random.choice(("color", "gray"))

    all_samples = []
    session = {
        "i": 0,
        "participant": participant,
        "condition": condition,
        "order": make_order(condition),
        "log": [],
        "current_image": None,
        "finished": False,
    }
    show_fixation(canvas, lambda: show_image(canvas, session))

def show_fixation(canvas, next_fn):
    """Draw a fixation cross on one side of the screen."""
    canvas.delete("all")
    side = random.choice(("left", "right"))
    cx = SCREEN_WIDTH * (0.25 if side == "left" else 0.75)
    cy = SCREEN_HEIGHT / 2
    canvas.create_line(cx - 20, cy, cx + 20, cy, fill=FIX_COLOR, width=3)
    canvas.create_line(cx, cy - 20, cx, cy + 20, fill=FIX_COLOR, width=3)
    root.after(FIX_MS, next_fn)

def show_image(canvas, state):
    """Show one centered image for IMG_MS."""
    global photo
    canvas.delete("all")
    if state["i"] >= len(state["order"]):
        finish_session(state)
        show_done(canvas)
        return
    path, _ = state["order"][state["i"]]
    image_name = path.stem
    photo = ImageTk.PhotoImage(Image.open(path).convert("RGB"))
    item = canvas.create_image(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, anchor="center", image=photo)
    x, y = canvas.coords(item)
    w, h = photo.width(), photo.height()
    state["log"].append({"order": state["i"] + 1, "theme": image_name,
                         "condition": state["condition"],
                         "img_x_px": x - w / 2, "img_y_px": y - h / 2,
                         "disp_w": w, "disp_h": h})

    # Start gaze recording when image appears
    state["current_image"] = image_name
    tracker.clear()
    tracker.start_recording()

    state["i"] += 1
    root.after(IMG_MS, lambda: finish_image(canvas, state))

def finish_image(canvas, state):
    """Stop recording and collect gaze samples after image disappears."""
    tracker.stop_recording()
    collect_samples(state)
    state["current_image"] = None

    show_fixation(canvas, lambda: show_image(canvas, state))

def collect_samples(state):
    """Add the samples of the last image to the session, labelled with the trial."""
    global all_samples

    samples = pd.DataFrame(tracker.get_samples())
    samples["image"] = state["current_image"]
    samples["order"] = state["i"]           # state["i"] was incremented when the image appeared
    samples["participant"] = state["participant"]
    samples["condition"] = state["condition"]
    all_samples.append(samples)

def save_gaze_data(state):
    """Save all gaze samples to a CSV named by participant."""
    global all_samples

    if not all_samples:
        print("No gaze samples recorded; gaze CSV not written.")
        return

    df = pd.concat(all_samples, ignore_index=True)
    output_file = OUTPUT_DIR / GAZE_FILE_TEMPLATE.format(participant=state["participant"])
    df.to_csv(output_file, index=False)

    print(f"Gaze data saved to: {output_file} ({len(df)} samples)")

def save_log(state):
    """Write the trial log to a CSV named by participant and condition."""
    output_file = OUTPUT_DIR / OUTPUT_FILE_TEMPLATE.format(participant=state["participant"], condition=state["condition"])

    pd.DataFrame(state["log"]).to_csv(output_file, index=False)

    print(f"Trial log saved to: {output_file}")

def finish_session(state):
    """Save the trial log and the gaze data once per session."""
    if state["finished"]:
        return
    state["finished"] = True
    save_log(state)
    save_gaze_data(state)

def quit_experiment(event=None):
    """Escape: keep what was recorded so far, then close."""
    global session

    if session is not None and not session["finished"]:
        try:
            if tracker is not None and tracker.is_recording():
                tracker.stop_recording()
                if session["current_image"] is not None:
                    collect_samples(session)
        except Exception as exc:
            print("Error while stopping the eye tracker:", exc)
        finish_session(session)

    root.destroy()

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
    root.bind("<Escape>", quit_experiment)
    root.focus_set()

    with hengam.EyeTracker(SCREEN_WIDTH, SCREEN_HEIGHT) as eye_tracker:
        tracker = eye_tracker

        ask_participant(canvas)
        root.mainloop()

if __name__ == "__main__":
    main()
