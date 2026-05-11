"""Loss functions.

We implement softmax + cross-entropy as a fused op rather than composing
log/softmax separately. Doing it that way is both numerically stable (we
subtract the per-row max before exponentiating) and gives a clean
gradient: `d/d logits = (softmax(logits) - one_hot(target)) / N`.
"""

from __future__ import annotations

import numpy as np

from .tensor import Tensor


def softmax_cross_entropy(logits: Tensor, targets: np.ndarray) -> Tensor:
    """Compute the mean cross-entropy loss over a batch.

    Parameters
    ----------
    logits : Tensor of shape (N, C)
        Raw class scores.
    targets : ndarray of shape (N,) with integer class labels in [0, C).
    """
    if logits.data.ndim != 2:
        raise ValueError(f"logits must be 2D (N, C); got shape {logits.shape}")
    targets = np.asarray(targets, dtype=np.int64)
    if targets.ndim != 1 or targets.shape[0] != logits.data.shape[0]:
        raise ValueError(
            f"targets shape {targets.shape} doesn't match logits batch {logits.shape[0]}"
        )

    N, C = logits.data.shape
    shifted = logits.data - logits.data.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    probs = exp / exp.sum(axis=1, keepdims=True)
    # Negative log-likelihood of the true class, averaged over the batch.
    eps = 1e-12
    nll = -np.log(probs[np.arange(N), targets] + eps).mean()

    out = Tensor(np.asarray(nll, dtype=np.float32), requires_grad=logits.requires_grad,
                 _prev=(logits,), _op="softmax_ce")

    def _bwd() -> None:
        if not logits.requires_grad:
            return
        logits._ensure_grad()
        d = probs.copy()
        d[np.arange(N), targets] -= 1.0
        d /= N
        # out.grad is a scalar; broadcast over (N, C).
        logits.grad = logits.grad + d * out.grad

    out._backward = _bwd
    return out
