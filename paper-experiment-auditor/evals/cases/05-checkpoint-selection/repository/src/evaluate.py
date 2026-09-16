from pathlib import Path


def checkpoint_for_test(directory="checkpoints"):
    checkpoints = sorted(Path(directory).glob("epoch_*.pt"))
    if not checkpoints:
        raise FileNotFoundError("no checkpoints")
    return checkpoints[-1]

