"""Train an MLP on MNIST.

Expects the four MNIST IDX files in a directory you pass via --data
(gzipped or plain). You can grab them from any reputable mirror; the
filenames must match the standard distribution:

    train-images-idx3-ubyte[.gz]
    train-labels-idx1-ubyte[.gz]
    t10k-images-idx3-ubyte[.gz]
    t10k-labels-idx1-ubyte[.gz]

Typical accuracy with the defaults below: ~98% on the test set after
10 epochs (a few minutes on CPU).

Run:
    python -m examples.train_mnist --data ~/datasets/mnist
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from tinynet import Adam, Linear, ReLU, Sequential, Tensor, softmax_cross_entropy
from tinynet.data import iterate_minibatches, load_mnist


def accuracy(logits: np.ndarray, y: np.ndarray) -> float:
    return float((logits.argmax(axis=1) == y).mean())


def evaluate(model, x: np.ndarray, y: np.ndarray, batch_size: int = 1000) -> float:
    correct = 0
    for i in range(0, len(x), batch_size):
        xb = x[i:i + batch_size]
        yb = y[i:i + batch_size]
        preds = model(Tensor(xb)).numpy().argmax(axis=1)
        correct += int((preds == yb).sum())
    return correct / len(x)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True,
                    help="Directory containing the four MNIST IDX files")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden", type=int, default=128)
    args = ap.parse_args()

    print(f"loading MNIST from {args.data}")
    x_train, y_train, x_test, y_test = load_mnist(args.data)
    print(f"train: {x_train.shape}, test: {x_test.shape}")

    model = Sequential(
        Linear(784, args.hidden),
        ReLU(),
        Linear(args.hidden, args.hidden),
        ReLU(),
        Linear(args.hidden, 10),
    )
    optimizer = Adam(model.parameters(), lr=args.lr)

    print(f"params: {sum(p.data.size for p in model.parameters())}")
    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        losses = []
        for xb, yb in iterate_minibatches(x_train, y_train, args.batch_size, seed=epoch):
            logits = model(Tensor(xb))
            loss = softmax_cross_entropy(logits, yb)
            model.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        test_acc = evaluate(model, x_test, y_test)
        print(f"epoch {epoch:2d} | loss {np.mean(losses):.4f} "
              f"| test_acc {test_acc:.4f} | {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
