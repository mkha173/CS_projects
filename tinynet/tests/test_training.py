"""Integration tests: actually train networks and verify they learn."""

from __future__ import annotations

import numpy as np
import pytest

from tinynet import Adam, Linear, ReLU, SGD, Sequential, Tensor, softmax_cross_entropy
from tinynet.data import iterate_minibatches, make_blobs, make_moons


def test_overfit_tiny_batch():
    """A small MLP must drive the loss near zero on a tiny memorisable batch."""
    np.random.seed(0)
    x = np.random.randn(16, 4).astype(np.float32)
    y = np.random.randint(0, 3, size=16).astype(np.int64)

    model = Sequential(
        Linear(4, 32),
        ReLU(),
        Linear(32, 3),
    )
    opt = Adam(model.parameters(), lr=1e-2)

    for _ in range(300):
        logits = model(Tensor(x))
        loss = softmax_cross_entropy(logits, y)
        model.zero_grad()
        loss.backward()
        opt.step()

    final = loss.item()
    preds = model(Tensor(x)).numpy().argmax(axis=1)
    accuracy = (preds == y).mean()
    assert final < 0.05, f"loss did not decrease enough: {final}"
    assert accuracy == 1.0, f"didn't fully memorise: acc={accuracy}"


def test_blobs_high_accuracy():
    """Linearly separable blobs should hit ~100% test accuracy."""
    x_train, y_train = make_blobs(600, n_classes=3, n_features=4, seed=0)
    x_test, y_test = make_blobs(200, n_classes=3, n_features=4, seed=0)

    model = Sequential(Linear(4, 16), ReLU(), Linear(16, 3))
    opt = Adam(model.parameters(), lr=5e-3)
    for epoch in range(20):
        for xb, yb in iterate_minibatches(x_train, y_train, 64, seed=epoch):
            logits = model(Tensor(xb))
            loss = softmax_cross_entropy(logits, yb)
            model.zero_grad()
            loss.backward()
            opt.step()
    acc = float((model(Tensor(x_test)).numpy().argmax(axis=1) == y_test).mean())
    assert acc > 0.95, f"blobs accuracy too low: {acc}"


def test_moons_non_linear_separation():
    """Non-linearly separable moons should still hit >90% with an MLP."""
    x_train, y_train = make_moons(800, noise=0.15, seed=0)
    x_test, y_test = make_moons(200, noise=0.15, seed=1)

    model = Sequential(
        Linear(2, 32),
        ReLU(),
        Linear(32, 32),
        ReLU(),
        Linear(32, 2),
    )
    opt = Adam(model.parameters(), lr=3e-3)
    for epoch in range(30):
        for xb, yb in iterate_minibatches(x_train, y_train, 64, seed=epoch):
            logits = model(Tensor(xb))
            loss = softmax_cross_entropy(logits, yb)
            model.zero_grad()
            loss.backward()
            opt.step()
    acc = float((model(Tensor(x_test)).numpy().argmax(axis=1) == y_test).mean())
    assert acc > 0.90, f"moons accuracy too low: {acc}"


def test_sgd_also_works():
    """A different optimizer (SGD with momentum) must also reduce loss."""
    np.random.seed(0)
    x = np.random.randn(64, 4).astype(np.float32)
    y = np.random.randint(0, 2, size=64).astype(np.int64)
    model = Sequential(Linear(4, 16), ReLU(), Linear(16, 2))
    opt = SGD(model.parameters(), lr=0.05, momentum=0.9)
    initial = softmax_cross_entropy(model(Tensor(x)), y).item()
    for _ in range(100):
        loss = softmax_cross_entropy(model(Tensor(x)), y)
        model.zero_grad()
        loss.backward()
        opt.step()
    final = loss.item()
    assert final < initial * 0.5, f"SGD didn't reduce loss enough: {initial} -> {final}"
