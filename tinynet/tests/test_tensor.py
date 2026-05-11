"""Gradient correctness tests.

We compare analytic gradients (from `Tensor.backward()`) against
numerical gradients computed via central differences. If the autograd
is wrong, the relative error blows up; if it's right, errors stay tiny.
"""

from __future__ import annotations

import numpy as np
import pytest

from tinynet.tensor import Tensor, relu


def _numerical_grad(f, x: np.ndarray, eps: float = 1e-3) -> np.ndarray:
    """Central-difference numerical gradient of scalar function f at x."""
    grad = np.zeros_like(x, dtype=np.float64)
    x_flat = x.reshape(-1)
    grad_flat = grad.reshape(-1)
    for i in range(x_flat.size):
        orig = x_flat[i]
        x_flat[i] = orig + eps
        plus = float(f(x))
        x_flat[i] = orig - eps
        minus = float(f(x))
        x_flat[i] = orig
        grad_flat[i] = (plus - minus) / (2 * eps)
    return grad.astype(np.float32)


def _check(name, analytic, numerical, atol=1e-2, rtol=1e-2):
    err = np.abs(analytic - numerical)
    rel = err / (np.abs(numerical) + 1e-6)
    assert np.all((err < atol) | (rel < rtol)), (
        f"{name} gradient mismatch:\n analytic={analytic}\n numerical={numerical}"
    )


def test_add_gradient():
    a_np = np.random.randn(3, 4).astype(np.float32)
    b_np = np.random.randn(4).astype(np.float32)  # broadcast

    def loss(a_val):
        a = Tensor(a_val, requires_grad=True)
        b = Tensor(b_np)
        return ((a + b) ** 2).sum().item()

    a = Tensor(a_np, requires_grad=True)
    b = Tensor(b_np, requires_grad=True)
    out = ((a + b) ** 2).sum()
    out.backward()

    num = _numerical_grad(loss, a_np.copy())
    _check("add (a)", a.grad, num)


def test_broadcast_bias_gradient():
    """Verify that a (D,) bias broadcast over (N, D) gets the right grad."""
    x_np = np.random.randn(5, 3).astype(np.float32)
    b_np = np.random.randn(3).astype(np.float32)

    def loss(b_val):
        x = Tensor(x_np)
        b = Tensor(b_val)
        return ((x + b) ** 2).sum().item()

    x = Tensor(x_np)
    b = Tensor(b_np, requires_grad=True)
    out = ((x + b) ** 2).sum()
    out.backward()

    num = _numerical_grad(loss, b_np.copy())
    _check("bias broadcast", b.grad, num)


def test_mul_gradient():
    a_np = np.random.randn(4).astype(np.float32)
    b_np = np.random.randn(4).astype(np.float32)

    def loss(a_val):
        a = Tensor(a_val)
        b = Tensor(b_np)
        return (a * b).sum().item()

    a = Tensor(a_np, requires_grad=True)
    b = Tensor(b_np)
    out = (a * b).sum()
    out.backward()
    num = _numerical_grad(loss, a_np.copy())
    _check("mul", a.grad, num)


def test_matmul_gradient():
    a_np = np.random.randn(3, 4).astype(np.float32)
    b_np = np.random.randn(4, 2).astype(np.float32)

    def loss(a_val):
        a = Tensor(a_val)
        b = Tensor(b_np)
        return ((a @ b) ** 2).sum().item()

    a = Tensor(a_np, requires_grad=True)
    b = Tensor(b_np)
    out = ((a @ b) ** 2).sum()
    out.backward()
    num = _numerical_grad(loss, a_np.copy())
    _check("matmul A", a.grad, num)

    # Now wrt B
    def loss_b(b_val):
        a = Tensor(a_np)
        b = Tensor(b_val)
        return ((a @ b) ** 2).sum().item()

    a = Tensor(a_np)
    b = Tensor(b_np, requires_grad=True)
    out = ((a @ b) ** 2).sum()
    out.backward()
    num = _numerical_grad(loss_b, b_np.copy())
    _check("matmul B", b.grad, num)


def test_relu_gradient():
    x_np = np.random.randn(10).astype(np.float32)
    # Avoid points near zero where the gradient is ambiguous numerically.
    x_np[np.abs(x_np) < 0.1] = 0.5

    def loss(x_val):
        x = Tensor(x_val)
        return (relu(x) ** 2).sum().item()

    x = Tensor(x_np, requires_grad=True)
    out = (relu(x) ** 2).sum()
    out.backward()
    num = _numerical_grad(loss, x_np.copy())
    _check("relu", x.grad, num)


def test_grad_accumulation():
    """Calling backward twice should accumulate, not overwrite."""
    x = Tensor(np.ones(3), requires_grad=True)
    y = x.sum()
    y.backward()
    first = x.grad.copy()
    y2 = x.sum()
    y2.backward()
    assert np.allclose(x.grad, 2 * first)


def test_zero_grad_clears():
    x = Tensor(np.ones(3), requires_grad=True)
    y = x.sum()
    y.backward()
    assert x.grad is not None
    x.zero_grad()
    assert x.grad is None
