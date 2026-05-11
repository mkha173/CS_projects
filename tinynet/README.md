# tinynet

A neural network library built from scratch in pure NumPy. No PyTorch, no TensorFlow, no JAX — just a small reverse-mode autograd engine and the layers/optimizers you need to train a real MLP.

## What's in it

A reverse-mode autograd `Tensor` (NumPy-backed) with operations for add, mul, matmul, sub, neg, pow, sum, mean, and ReLU. Each op builds a node in the computation graph; calling `.backward()` on a scalar walks the graph in reverse-topological order and accumulates gradients into every leaf tensor with `requires_grad=True`. Broadcasting is handled correctly — bias gradients are summed over the batch axis automatically.

On top of that sits a small `nn` module with a PyTorch-flavored `Module` base class plus `Linear`, `ReLU`, and `Sequential`. The softmax cross-entropy loss is implemented as a fused op for numerical stability. Optimizers include SGD with momentum and Adam with bias correction.

The data module loads MNIST from the standard IDX file format (gzipped or plain) and includes synthetic dataset generators (two-moons and Gaussian blobs) so you can verify everything works without a download.

## Run the synthetic demo

```bash
pip install numpy
python -m examples.train_synthetic
```

You should see the loss drop and test accuracy climb past 95% on the two-moons problem within 30 epochs.

## Train on MNIST

Drop the four IDX files into a directory:

```
mnist/
  train-images-idx3-ubyte.gz
  train-labels-idx1-ubyte.gz
  t10k-images-idx3-ubyte.gz
  t10k-labels-idx1-ubyte.gz
```

Then:

```bash
python -m examples.train_mnist --data ./mnist --epochs 10
```

Expected: ~98% test accuracy in a few minutes on CPU with the default 784→128→128→10 architecture.

## Tests

```bash
pip install pytest
pytest -v
```

The suite covers three concerns:

1. **Gradient correctness** — every op's analytic gradient is checked against a central-difference numerical gradient. If the autograd is wrong, these tests blow up immediately.
2. **Layer behavior** — `Linear`/`Sequential`/parameter collection, softmax cross-entropy values and gradient sums.
3. **Training works** — overfitting a tiny memorisable batch (must reach 100% accuracy), training on linearly separable blobs (>95% test acc), and the non-linear two-moons problem (>90% test acc). A separate test verifies SGD also reduces the loss.

## Layout

```
tinynet/
  tensor.py    # autograd Tensor + ops + relu
  nn.py        # Module, Linear, ReLU, Sequential
  losses.py    # softmax_cross_entropy (fused, numerically stable)
  optim.py     # SGD, Adam
  data.py      # MNIST IDX loader + synthetic datasets + batching
examples/
  train_synthetic.py
  train_mnist.py
tests/
  test_tensor.py     # gradient checks
  test_nn.py         # layer + loss tests
  test_training.py   # end-to-end training
```

## Design choices and limitations

The matmul op only supports 2-D tensors. That's enough for MLPs but rules out batched matmul, which you'd want for transformers. The reduction ops `sum`/`mean` only take a single int axis or `None` — no tuple of axes. No GPU, no convolution, no batchnorm, no dropout. Adding any of those is mostly a matter of writing one more op with its backward pass; the autograd engine doesn't need to change.

The Module API is single-pass: a fresh forward graph is built on every call, so there's no need for an explicit `eval()` mode. That keeps the surface area small but means you'd want to add per-tensor caching if you ever extend this with something like a recurrent net.
