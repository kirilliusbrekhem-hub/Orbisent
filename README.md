# Orbisent
Beyond the Known.

Orbisent is a long-term project to build a custom AI agent around a language model that we train ourselves,
starting from randomly initialized weights rather than a pretrained model.
Everything runs in the cloud (GitHub + Google Colab), with no local Python or GPU needed.

## Current status: Experiment 01

The first step is the **neural core**: proving we can train a small language model from scratch, end to end.

[`notebooks/01_train_from_scratch.ipynb`](notebooks/01_train_from_scratch.ipynb) trains a tiny character-level
GPT-style Transformer in PyTorch on *Tiny Shakespeare* (public domain). It covers:

- a simple character tokenizer and a train/validation split
- a small Transformer written from scratch, with randomly initialized weights
- next-character training with cross-entropy loss, plus initial vs. final loss
- text generation from a short prompt
- saving and downloading a checkpoint (weights + configuration)
- automatic GPU detection, with a short CPU smoke-test fallback for the free Colab tier

See [`notebooks/README.md`](notebooks/README.md) for how to open and run it in Colab.

## Ground rules

- No pretrained models, pretrained weights, external inference APIs or paid services.
- Datasets, checkpoints, model weights and secrets are never committed to this repository.
- The agent itself comes later; for now the work is the model.
