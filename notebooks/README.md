# Orbisent notebooks

*Beyond the Known.*

These notebooks run in **Google Colab**, so you don't need Python or a GPU on your own computer.

| Notebook | What it does |
| --- | --- |
| [`01_train_from_scratch.ipynb`](01_train_from_scratch.ipynb) | Trains a tiny character-level GPT-style Transformer from randomly initialized weights on Tiny Shakespeare (public domain). |

## Opening a notebook in Google Colab

**Option A: direct link (once the notebook is on the `main` branch)**

<https://colab.research.google.com/github/kirilliusbrekhem-hub/Orbisent/blob/main/notebooks/01_train_from_scratch.ipynb>

To open the version on a different branch, replace `main` in the link with the branch name.

**Option B: from inside Colab**

1. Go to <https://colab.research.google.com>.
2. Choose **File → Open notebook → GitHub**.
3. Enter `kirilliusbrekhem-hub/Orbisent`, pick the branch, and select `notebooks/01_train_from_scratch.ipynb`.
   If the repository is private, tick **Include private repos** and allow Colab to access your GitHub account.

## Running it

1. *(Optional but recommended)* **Runtime → Change runtime type → T4 GPU → Save.**
   The free tier does **not guarantee** a GPU, and sessions can stop or disconnect without warning.
2. **Runtime → Run all.**
3. The notebook detects the hardware itself:
   * **GPU available:** it runs the `gpu` configuration (a few thousand training steps, usually around 5–15 minutes).
   * **No GPU:** it runs the short `smoke_test` configuration (about a minute on a CPU). This only checks that the code works,
     so the generated text will mostly be gibberish.
   * To force the quick version on a GPU, set `FORCE_SMOKE_TEST = True` in the configuration cell.
4. At the end, the checkpoint (`checkpoints/orbisent_exp01_<config>.pt`) is saved and your browser offers to download it.
   You can also download it from Colab's file browser (folder icon on the left) or copy it to Google Drive with the commented-out lines in the last code cell.

## Rules for this folder

* Commit notebooks **without** large outputs where possible (*Edit → Clear all outputs* before saving to GitHub).
* Never commit datasets, checkpoints (`*.pt`), model weights or secrets. `.gitignore` blocks the common file types.
* No pretrained models, external inference APIs or paid services: everything is trained from scratch.
