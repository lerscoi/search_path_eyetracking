# Eyetracking Experiment
# Search strategies between colored and grayscale images

## Overview

Participants view images photographs one at a time (5s each), each with a small T or L letter hidden in a busy (high-entropy) image region. Between images, a fixation cross appears on the left or right of the screen (3s). Each participant is randomly assigned to see either the **color** or the **grayscale** version of every image. 

## Preparing the stimuli

1. Download the OASIS dataset ([https://www.oasisbrains.org — image archive](https://db.tt/yYTZYCga) with `oasis.csv` metadata).
2. Copy the images you want to use into a `candidates/` folder.
3. Run:

   ```
   python create_stimuli.py
   ```

   This:
   - matches candidate filenames against `oasis.csv` and writes `selected.csv`,
   - normalizes contrast and saves color + Gleam grayscale versions,
   - hides a marker in each image at a high-entropy spot outside the central region, blended with the local pixel mean,
   - writes `final_color/` and `final_gray/` and the marker positions in `targets.csv`.

## Running the experiment

```
python run_experiment.py
```

- Enter the participant number, press Enter, then press SPACE on the instruction screen.
- Each trial: fixation cross (3s, left or right), followed by an image (5s, centered). 
- Escape allows participant to quit experiment at any time.
- Output: `experiment_log_<participant>_<condition>.csv` with trial order, image name, and on-screen position.
