"""Train a small MLP on a synthetic two-moons dataset.

This script doesn't need any external data - it generates the dataset
in-process and trains the same model architecture used for MNIST.
Great for confirming everything works end-to-end without downloads.

Run:
    python -m examples.train_synthetic
"""

from __future__ import annotations

import time

import numpy as np

from tinynet import Adam, Linear, ReLU, Sequential, Tensor, softmax_cross_entropy
from tinynet.data import iterate_minibatches, make_moons


def accuracy(logits: np.ndarray, y: np.ndarray) -> float:
    return float((logits.argmax(axis=1) == y).mean())


def main() -> None:
    np.random.seed(0)
    x_train, y_train = make_moons(2000, noise=0.2, seed=0)
    x_test, y_test = make_moons(500, noise=0.2, seed=1)

    model = Sequential(
        Linear(2, 32),
        ReLU(),
        Linear(32, 32),
        ReLU(),
        Linear(32, 2),
    )
    optimizer = Adam(model.parameters(), lr=3e-3)

    epochs = 30
    batch_size = 64
    print(f"params: {sum(p.data.size for p in model.parameters())}")
    start = time.time()
    for epoch in range(1, epochs + 1):
        losses = []
        for xb, yb in iterate_minibatches(x_train, y_train, batch_size, seed=epoch):
            logits = model(Tensor(xb))
            loss = softmax_cross_entropy(logits, yb)
            model.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        train_logits = model(Tensor(x_train)).numpy()
        test_logits = model(Tensor(x_test)).numpy()
        print(f"epoch {epoch:3d} | loss {np.mean(losses):.4f} "
              f"| train_acc {accuracy(train_logits, y_train):.3f} "
              f"| test_acc  {accuracy(test_logits, y_test):.3f}")
    print(f"finished in {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
