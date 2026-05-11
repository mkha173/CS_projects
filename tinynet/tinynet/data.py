"""Data utilities: MNIST IDX loader, synthetic datasets, batching."""

from __future__ import annotations

import gzip
import struct
from pathlib import Path
from typing import Iterator, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# MNIST
# ---------------------------------------------------------------------------

def load_idx(path: str | Path) -> np.ndarray:
    """Load a single IDX file (gzip-compressed or plain)."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as f:
        magic = struct.unpack(">I", f.read(4))[0]
        ndim = magic & 0xff
        shape = struct.unpack(">" + "I" * ndim, f.read(4 * ndim))
        return np.frombuffer(f.read(), dtype=np.uint8).reshape(shape)


def load_mnist(root: str | Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load MNIST from a directory containing the four IDX files.

    Expected filenames (matching the standard distribution):
        train-images-idx3-ubyte[.gz]
        train-labels-idx1-ubyte[.gz]
        t10k-images-idx3-ubyte[.gz]
        t10k-labels-idx1-ubyte[.gz]

    Returns (x_train, y_train, x_test, y_test).
    Pixel values are float32 in [0, 1]; labels are int64.
    """
    root = Path(root)

    def find(prefix: str) -> Path:
        for ext in (".gz", ""):
            p = root / f"{prefix}{ext}"
            if p.exists():
                return p
        raise FileNotFoundError(f"could not find {prefix}[.gz] in {root}")

    x_train = load_idx(find("train-images-idx3-ubyte"))
    y_train = load_idx(find("train-labels-idx1-ubyte"))
    x_test = load_idx(find("t10k-images-idx3-ubyte"))
    y_test = load_idx(find("t10k-labels-idx1-ubyte"))

    x_train = x_train.reshape(x_train.shape[0], -1).astype(np.float32) / 255.0
    x_test = x_test.reshape(x_test.shape[0], -1).astype(np.float32) / 255.0
    return x_train, y_train.astype(np.int64), x_test, y_test.astype(np.int64)


# ---------------------------------------------------------------------------
# Synthetic datasets - useful for tests and demos that don't need MNIST.
# ---------------------------------------------------------------------------

def make_moons(n_samples: int, noise: float = 0.1, seed: int = 0
              ) -> Tuple[np.ndarray, np.ndarray]:
    """Two interleaving half-circles - a classic non-linear binary problem."""
    rng = np.random.default_rng(seed)
    n1 = n_samples // 2
    n2 = n_samples - n1
    t1 = rng.uniform(0.0, np.pi, n1)
    t2 = rng.uniform(0.0, np.pi, n2)
    x1 = np.stack([np.cos(t1), np.sin(t1)], axis=1)
    x2 = np.stack([1.0 - np.cos(t2), 0.5 - np.sin(t2)], axis=1)
    x = np.concatenate([x1, x2]).astype(np.float32)
    x += rng.normal(0.0, noise, x.shape).astype(np.float32)
    y = np.concatenate([
        np.zeros(n1, dtype=np.int64),
        np.ones(n2, dtype=np.int64),
    ])
    perm = rng.permutation(n_samples)
    return x[perm], y[perm]


def make_blobs(n_samples: int, n_classes: int = 3, n_features: int = 2,
               seed: int = 0) -> Tuple[np.ndarray, np.ndarray]:
    """Isotropic Gaussian blobs - a linearly separable multi-class problem."""
    rng = np.random.default_rng(seed)
    per_class = n_samples // n_classes
    centers = rng.uniform(-5.0, 5.0, size=(n_classes, n_features))
    xs, ys = [], []
    for c in range(n_classes):
        xs.append(rng.normal(centers[c], 0.8, size=(per_class, n_features)))
        ys.append(np.full(per_class, c, dtype=np.int64))
    x = np.concatenate(xs).astype(np.float32)
    y = np.concatenate(ys)
    perm = rng.permutation(len(x))
    return x[perm], y[perm]


# ---------------------------------------------------------------------------
# Batching
# ---------------------------------------------------------------------------

def iterate_minibatches(
    x: np.ndarray,
    y: np.ndarray,
    batch_size: int,
    shuffle: bool = True,
    seed: int | None = None,
) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
    """Yield (x_batch, y_batch) tuples; optionally reshuffled each epoch."""
    n = x.shape[0]
    indices = np.arange(n)
    if shuffle:
        rng = np.random.default_rng(seed)
        rng.shuffle(indices)
    for start in range(0, n, batch_size):
        idx = indices[start:start + batch_size]
        yield x[idx], y[idx]
