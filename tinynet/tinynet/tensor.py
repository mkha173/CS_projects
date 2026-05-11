"""Reverse-mode autograd Tensor backed by NumPy.

A Tensor wraps a numpy array and (optionally) tracks the operation that
produced it. Calling `.backward()` on a scalar output walks the
computation graph in reverse-topological order, accumulating gradients
into every tensor that has `requires_grad=True`.

Design notes
------------
* Each op constructs a new Tensor with `_prev` (parent tensors) and
  `_backward` (a closure that pushes gradients from this tensor to its
  parents).
* Gradients are accumulated, so the same parameter can appear multiple
  times in a graph without losing updates.
* Broadcasting is handled by `_unbroadcast`, which sums the incoming
  gradient over axes that were broadcast in the forward pass.

We keep the surface area small: just enough ops to train a fully
connected classifier (matmul, add, mul, neg/sub, sum, mean, relu).
The softmax cross-entropy is provided as a fused op in losses.py for
numerical stability.
"""

from __future__ import annotations

from typing import Iterable, Tuple, Union

import numpy as np


ArrayLike = Union[np.ndarray, float, int, list, tuple]


def _unbroadcast(grad: np.ndarray, target_shape: Tuple[int, ...]) -> np.ndarray:
    """Reduce `grad` so its shape matches `target_shape`.

    Used after broadcasting: if a (3,) bias was broadcast to (N, 3) in
    the forward pass, the gradient at the bias position is summed over
    the batch axis on the backward pass.
    """
    # Drop any leading dims that don't exist in the target shape.
    while grad.ndim > len(target_shape):
        grad = grad.sum(axis=0)
    # Sum over axes where the target dim was 1 (broadcast).
    for axis, dim in enumerate(target_shape):
        if dim == 1 and grad.shape[axis] != 1:
            grad = grad.sum(axis=axis, keepdims=True)
    return grad


class Tensor:
    __slots__ = ("data", "requires_grad", "grad", "_prev", "_backward", "_op")

    def __init__(
        self,
        data: ArrayLike,
        requires_grad: bool = False,
        _prev: Tuple["Tensor", ...] = (),
        _op: str = "",
    ) -> None:
        if isinstance(data, np.ndarray):
            self.data = data.astype(np.float32, copy=False)
        else:
            self.data = np.asarray(data, dtype=np.float32)
        self.requires_grad = requires_grad
        self.grad: np.ndarray | None = None
        self._prev = _prev
        self._backward = _noop
        self._op = _op

    # ------------------------------------------------------------------
    # Basic introspection
    # ------------------------------------------------------------------
    @property
    def shape(self) -> Tuple[int, ...]:
        return self.data.shape

    @property
    def ndim(self) -> int:
        return self.data.ndim

    def __repr__(self) -> str:
        return f"Tensor(shape={self.shape}, op={self._op!r}, requires_grad={self.requires_grad})"

    def numpy(self) -> np.ndarray:
        return self.data

    def item(self) -> float:
        return float(self.data.reshape(-1)[0])

    # ------------------------------------------------------------------
    # Grad bookkeeping
    # ------------------------------------------------------------------
    def _ensure_grad(self) -> None:
        if self.grad is None:
            self.grad = np.zeros_like(self.data)

    def zero_grad(self) -> None:
        self.grad = None

    def backward(self, grad: np.ndarray | None = None) -> None:
        if grad is None:
            if self.data.size != 1:
                raise RuntimeError(
                    "backward() on non-scalar Tensor requires an explicit grad"
                )
            grad = np.ones_like(self.data)
        self._ensure_grad()
        self.grad = self.grad + grad

        # Topological sort: visit parents before children, reverse for backward.
        topo: list[Tensor] = []
        visited: set[int] = set()

        def build(t: Tensor) -> None:
            if id(t) in visited:
                return
            visited.add(id(t))
            for p in t._prev:
                build(p)
            topo.append(t)

        build(self)
        for t in reversed(topo):
            t._backward()

    # ------------------------------------------------------------------
    # Arithmetic ops
    # ------------------------------------------------------------------
    def __add__(self, other) -> "Tensor":
        return _add(self, _as_tensor(other))

    def __radd__(self, other) -> "Tensor":
        return _add(_as_tensor(other), self)

    def __sub__(self, other) -> "Tensor":
        return _add(self, -_as_tensor(other))

    def __rsub__(self, other) -> "Tensor":
        return _add(_as_tensor(other), -self)

    def __neg__(self) -> "Tensor":
        return _mul(self, _as_tensor(-1.0))

    def __mul__(self, other) -> "Tensor":
        return _mul(self, _as_tensor(other))

    def __rmul__(self, other) -> "Tensor":
        return _mul(_as_tensor(other), self)

    def __truediv__(self, other) -> "Tensor":
        return _mul(self, _as_tensor(other) ** -1)

    def __pow__(self, p: float) -> "Tensor":
        return _pow(self, float(p))

    def __matmul__(self, other) -> "Tensor":
        return _matmul(self, _as_tensor(other))

    # ------------------------------------------------------------------
    # Reductions / shape
    # ------------------------------------------------------------------
    def sum(self, axis: int | None = None, keepdims: bool = False) -> "Tensor":
        return _sum(self, axis, keepdims)

    def mean(self, axis: int | None = None, keepdims: bool = False) -> "Tensor":
        s = self.sum(axis=axis, keepdims=keepdims)
        if axis is None:
            n = self.data.size
        else:
            n = self.data.shape[axis]
        return s * (1.0 / n)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _noop() -> None:
    pass


def _as_tensor(x) -> Tensor:
    return x if isinstance(x, Tensor) else Tensor(x)


# ---------------------------------------------------------------------------
# Ops
# ---------------------------------------------------------------------------

def _add(a: Tensor, b: Tensor) -> Tensor:
    out = Tensor(
        a.data + b.data,
        requires_grad=(a.requires_grad or b.requires_grad),
        _prev=(a, b),
        _op="add",
    )

    def _bwd() -> None:
        if a.requires_grad:
            a._ensure_grad()
            a.grad = a.grad + _unbroadcast(out.grad, a.data.shape)
        if b.requires_grad:
            b._ensure_grad()
            b.grad = b.grad + _unbroadcast(out.grad, b.data.shape)

    out._backward = _bwd
    return out


def _mul(a: Tensor, b: Tensor) -> Tensor:
    out = Tensor(
        a.data * b.data,
        requires_grad=(a.requires_grad or b.requires_grad),
        _prev=(a, b),
        _op="mul",
    )

    def _bwd() -> None:
        if a.requires_grad:
            a._ensure_grad()
            a.grad = a.grad + _unbroadcast(out.grad * b.data, a.data.shape)
        if b.requires_grad:
            b._ensure_grad()
            b.grad = b.grad + _unbroadcast(out.grad * a.data, b.data.shape)

    out._backward = _bwd
    return out


def _pow(a: Tensor, p: float) -> Tensor:
    out = Tensor(a.data ** p, requires_grad=a.requires_grad, _prev=(a,), _op=f"pow({p})")

    def _bwd() -> None:
        if a.requires_grad:
            a._ensure_grad()
            a.grad = a.grad + out.grad * (p * a.data ** (p - 1))

    out._backward = _bwd
    return out


def _matmul(a: Tensor, b: Tensor) -> Tensor:
    if a.data.ndim != 2 or b.data.ndim != 2:
        raise ValueError("matmul currently supports 2-D tensors only")
    out = Tensor(
        a.data @ b.data,
        requires_grad=(a.requires_grad or b.requires_grad),
        _prev=(a, b),
        _op="matmul",
    )

    def _bwd() -> None:
        if a.requires_grad:
            a._ensure_grad()
            a.grad = a.grad + out.grad @ b.data.T
        if b.requires_grad:
            b._ensure_grad()
            b.grad = b.grad + a.data.T @ out.grad

    out._backward = _bwd
    return out


def _sum(a: Tensor, axis: int | None, keepdims: bool) -> Tensor:
    out_data = a.data.sum(axis=axis, keepdims=keepdims)
    out = Tensor(out_data, requires_grad=a.requires_grad, _prev=(a,), _op="sum")

    def _bwd() -> None:
        if not a.requires_grad:
            return
        a._ensure_grad()
        g = out.grad
        if axis is not None and not keepdims:
            g = np.expand_dims(g, axis=axis)
        a.grad = a.grad + np.broadcast_to(g, a.data.shape).copy()

    out._backward = _bwd
    return out


def relu(x: Tensor) -> Tensor:
    """Rectified linear unit activation."""
    mask = (x.data > 0).astype(np.float32)
    out = Tensor(x.data * mask, requires_grad=x.requires_grad, _prev=(x,), _op="relu")

    def _bwd() -> None:
        if x.requires_grad:
            x._ensure_grad()
            x.grad = x.grad + out.grad * mask

    out._backward = _bwd
    return out
