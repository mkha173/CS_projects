"""Layer primitives and Module base class.

The Module API is intentionally PyTorch-flavored so the rest of the code
reads naturally: `model = Sequential(Linear(784, 128), ReLU(), Linear(128, 10))`.
"""

from __future__ import annotations

import math
from typing import Iterable, Iterator, List

import numpy as np

from .tensor import Tensor, relu


class Module:
    """Base class - tracks parameters via attribute walking."""

    def parameters(self) -> Iterator[Tensor]:
        seen: set[int] = set()
        for value in self._iter_children():
            if isinstance(value, Tensor) and value.requires_grad:
                if id(value) in seen:
                    continue
                seen.add(id(value))
                yield value
            elif isinstance(value, Module):
                for p in value.parameters():
                    if id(p) in seen:
                        continue
                    seen.add(id(p))
                    yield p

    def _iter_children(self) -> Iterable[object]:
        # Walk __dict__ for Tensors, Modules, and lists thereof.
        for v in self.__dict__.values():
            if isinstance(v, (Tensor, Module)):
                yield v
            elif isinstance(v, (list, tuple)):
                for item in v:
                    if isinstance(item, (Tensor, Module)):
                        yield item

    def zero_grad(self) -> None:
        for p in self.parameters():
            p.grad = None

    def __call__(self, *args, **kwargs):
        return self.forward(*args, **kwargs)

    def forward(self, *args, **kwargs):  # pragma: no cover - abstract
        raise NotImplementedError


class Linear(Module):
    """Affine transform y = x @ W + b.

    Uses Kaiming uniform initialisation, which works well for ReLU MLPs.
    """

    def __init__(self, in_features: int, out_features: int, *, bias: bool = True) -> None:
        # Kaiming uniform: bound = sqrt(6 / fan_in)
        bound = math.sqrt(6.0 / in_features)
        w = np.random.uniform(-bound, bound, size=(in_features, out_features)).astype(np.float32)
        self.weight = Tensor(w, requires_grad=True)
        if bias:
            self.bias = Tensor(np.zeros(out_features, dtype=np.float32), requires_grad=True)
        else:
            self.bias = None
        self.in_features = in_features
        self.out_features = out_features

    def forward(self, x: Tensor) -> Tensor:
        y = x @ self.weight
        if self.bias is not None:
            y = y + self.bias
        return y


class ReLU(Module):
    def forward(self, x: Tensor) -> Tensor:
        return relu(x)


class Sequential(Module):
    """Chain of modules applied in order."""

    def __init__(self, *layers: Module) -> None:
        self.layers: List[Module] = list(layers)

    def forward(self, x: Tensor) -> Tensor:
        for layer in self.layers:
            x = layer(x)
        return x

    def parameters(self) -> Iterator[Tensor]:
        seen: set[int] = set()
        for layer in self.layers:
            if isinstance(layer, Module):
                for p in layer.parameters():
                    if id(p) in seen:
                        continue
                    seen.add(id(p))
                    yield p
