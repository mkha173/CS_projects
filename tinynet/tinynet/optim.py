"""Stochastic optimizers."""

from __future__ import annotations

from typing import Iterable, List

import numpy as np

from .tensor import Tensor


class _Optimizer:
    def __init__(self, params: Iterable[Tensor]) -> None:
        self.params: List[Tensor] = list(params)

    def zero_grad(self) -> None:
        for p in self.params:
            p.grad = None

    def step(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError


class SGD(_Optimizer):
    """Stochastic gradient descent with optional momentum."""

    def __init__(self, params: Iterable[Tensor], lr: float, momentum: float = 0.0) -> None:
        super().__init__(params)
        self.lr = lr
        self.momentum = momentum
        self.velocity: List[np.ndarray] = [np.zeros_like(p.data) for p in self.params]

    def step(self) -> None:
        for p, v in zip(self.params, self.velocity):
            if p.grad is None:
                continue
            v *= self.momentum
            v += p.grad
            p.data -= self.lr * v


class Adam(_Optimizer):
    """Adam optimizer (Kingma & Ba, 2014) with bias correction."""

    def __init__(
        self,
        params: Iterable[Tensor],
        lr: float = 1e-3,
        betas: tuple = (0.9, 0.999),
        eps: float = 1e-8,
    ) -> None:
        super().__init__(params)
        self.lr = lr
        self.b1, self.b2 = betas
        self.eps = eps
        self.t = 0
        self.m: List[np.ndarray] = [np.zeros_like(p.data) for p in self.params]
        self.v: List[np.ndarray] = [np.zeros_like(p.data) for p in self.params]

    def step(self) -> None:
        self.t += 1
        bc1 = 1.0 - self.b1 ** self.t
        bc2 = 1.0 - self.b2 ** self.t
        for p, m, v in zip(self.params, self.m, self.v):
            if p.grad is None:
                continue
            g = p.grad
            m *= self.b1
            m += (1.0 - self.b1) * g
            v *= self.b2
            v += (1.0 - self.b2) * (g * g)
            m_hat = m / bc1
            v_hat = v / bc2
            p.data -= self.lr * m_hat / (np.sqrt(v_hat) + self.eps)
