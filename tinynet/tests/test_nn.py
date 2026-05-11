"""Tests for the Module / Linear / Sequential machinery and the loss."""

from __future__ import annotations

import numpy as np
import pytest

from tinynet import Linear, ReLU, Sequential, Tensor, softmax_cross_entropy


def test_linear_shapes():
    layer = Linear(5, 3)
    x = Tensor(np.random.randn(4, 5).astype(np.float32))
    y = layer(x)
    assert y.shape == (4, 3)


def test_sequential_parameters_unique_and_ordered():
    model = Sequential(
        Linear(2, 4),
        ReLU(),
        Linear(4, 3),
    )
    params = list(model.parameters())
    # 2 Linears * (weight + bias) = 4 parameters
    assert len(params) == 4
    # All distinct
    assert len({id(p) for p in params}) == 4


def test_zero_grad():
    layer = Linear(3, 2)
    x = Tensor(np.random.randn(2, 3).astype(np.float32))
    y = layer(x).sum()
    y.backward()
    for p in layer.parameters():
        assert p.grad is not None
    layer.zero_grad()
    for p in layer.parameters():
        assert p.grad is None


def test_softmax_cross_entropy_value():
    """For uniform logits, CE should equal log(C)."""
    logits = Tensor(np.zeros((4, 5), dtype=np.float32))
    y = np.zeros(4, dtype=np.int64)
    loss = softmax_cross_entropy(logits, y)
    assert abs(loss.item() - np.log(5)) < 1e-5


def test_softmax_cross_entropy_gradient_sums_to_zero():
    """The grad of softmax-CE over the class axis should sum to zero per row."""
    np.random.seed(7)
    logits = Tensor(np.random.randn(6, 4).astype(np.float32), requires_grad=True)
    y = np.array([0, 1, 2, 3, 0, 1], dtype=np.int64)
    loss = softmax_cross_entropy(logits, y)
    loss.backward()
    # Each row's gradient is (softmax - one_hot)/N, so each row sums to 0.
    row_sums = logits.grad.sum(axis=1)
    assert np.allclose(row_sums, 0, atol=1e-5)


def test_softmax_cross_entropy_perfect_prediction():
    """Very confident correct predictions give near-zero loss."""
    logits = Tensor(np.array([[10.0, 0.0], [0.0, 10.0]], dtype=np.float32))
    y = np.array([0, 1], dtype=np.int64)
    loss = softmax_cross_entropy(logits, y)
    assert loss.item() < 1e-3
