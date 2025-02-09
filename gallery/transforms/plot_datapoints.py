"""
==============
Datapoints FAQ
==============

.. note::
    Try on `collab <https://colab.research.google.com/github/pytorch/vision/blob/gh-pages/main/_generated_ipynb_notebooks/plot_datapoints.ipynb>`_
    or :ref:`go to the end <sphx_glr_download_auto_examples_transforms_plot_datapoints.py>` to download the full example code.


Datapoints are Tensor subclasses introduced together with
``torchvision.transforms.v2``. This example showcases what these datapoints are
and how they behave.

.. warning::

    **Intended Audience** Unless you're writing your own transforms or your own datapoints, you
    probably do not need to read this guide. This is a fairly low-level topic
    that most users will not need to worry about: you do not need to understand
    the internals of datapoints to efficiently rely on
    ``torchvision.transforms.v2``. It may however be useful for advanced users
    trying to implement their own datasets, transforms, or work directly with
    the datapoints.
"""

# %%
import PIL.Image

import torch
from torchvision import datapoints


# %%
# What are datapoints?
# --------------------
#
# Datapoints are zero-copy tensor subclasses:

tensor = torch.rand(3, 256, 256)
image = datapoints.Image(tensor)

assert isinstance(image, torch.Tensor)
assert image.data_ptr() == tensor.data_ptr()

# %%
# Under the hood, they are needed in :mod:`torchvision.transforms.v2` to correctly dispatch to the appropriate function
# for the input data.
#
# :mod:`torchvision.datapoints` supports four types of datapoints:
#
# * :class:`~torchvision.datapoints.Image`
# * :class:`~torchvision.datapoints.Video`
# * :class:`~torchvision.datapoints.BoundingBoxes`
# * :class:`~torchvision.datapoints.Mask`
#
# What can I do with a datapoint?
# -------------------------------
#
# Datapoints look and feel just like regular tensors - they **are** tensors.
# Everything that is supported on a plain :class:`torch.Tensor` like ``.sum()`` or
# any ``torch.*`` operator will also work on datapoints. See
# :ref:`datapoint_unwrapping_behaviour` for a few gotchas.

# %%
# .. _datapoint_creation:
#
# How do I construct a datapoint?
# -------------------------------
#
# Using the constructor
# ^^^^^^^^^^^^^^^^^^^^^
#
# Each datapoint class takes any tensor-like data that can be turned into a :class:`~torch.Tensor`

image = datapoints.Image([[[[0, 1], [1, 0]]]])
print(image)


# %%
# Similar to other PyTorch creations ops, the constructor also takes the ``dtype``, ``device``, and ``requires_grad``
# parameters.

float_image = datapoints.Image([[[0, 1], [1, 0]]], dtype=torch.float32, requires_grad=True)
print(float_image)


# %%
# In addition, :class:`~torchvision.datapoints.Image` and :class:`~torchvision.datapoints.Mask` can also take a
# :class:`PIL.Image.Image` directly:

image = datapoints.Image(PIL.Image.open("../assets/astronaut.jpg"))
print(image.shape, image.dtype)

# %%
# Some datapoints require additional metadata to be passed in ordered to be constructed. For example,
# :class:`~torchvision.datapoints.BoundingBoxes` requires the coordinate format as well as the size of the
# corresponding image (``canvas_size``) alongside the actual values. These
# metadata are required to properly transform the bounding boxes.

bboxes = datapoints.BoundingBoxes(
    [[17, 16, 344, 495], [0, 10, 0, 10]],
    format=datapoints.BoundingBoxFormat.XYXY,
    canvas_size=image.shape[-2:]
)
print(bboxes)

# %%
# Using ``datapoints.wrap()``
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^
#
# You can also use the :func:`~torchvision.datapoints.wrap` function to wrap a tensor object
# into a datapoint. This is useful when you already have an object of the
# desired type, which typically happens when writing transforms: you just want
# to wrap the output like the input.

new_bboxes = torch.tensor([0, 20, 30, 40])
new_bboxes = datapoints.wrap(new_bboxes, like=bboxes)
assert isinstance(new_bboxes, datapoints.BoundingBoxes)
assert new_bboxes.canvas_size == bboxes.canvas_size

# %%
# The metadata of ``new_bboxes`` is the same as ``bboxes``, but you could pass
# it as a parameter to override it.
#
# .. _datapoint_unwrapping_behaviour:
#
# I had a Datapoint but now I have a Tensor. Help!
# ------------------------------------------------
#
# By default, operations on :class:`~torchvision.datapoints.Datapoint` objects
# will return a pure Tensor:


assert isinstance(bboxes, datapoints.BoundingBoxes)

# Shift bboxes by 3 pixels in both H and W
new_bboxes = bboxes + 3

assert isinstance(new_bboxes, torch.Tensor)
assert not isinstance(new_bboxes, datapoints.BoundingBoxes)

# %%
# .. note::
#
#    This behavior only affects native ``torch`` operations. If you are using
#    the built-in ``torchvision`` transforms or functionals, you will always get
#    as output the same type that you passed as input (pure ``Tensor`` or
#    ``Datapoint``).

# %%
# But I want a Datapoint back!
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#
# You can re-wrap a pure tensor into a datapoint by just calling the datapoint
# constructor, or by using the :func:`~torchvision.datapoints.wrap` function
# (see more details above in :ref:`datapoint_creation`):

new_bboxes = bboxes + 3
new_bboxes = datapoints.wrap(new_bboxes, like=bboxes)
assert isinstance(new_bboxes, datapoints.BoundingBoxes)

# %%
# Alternatively, you can use the :func:`~torchvision.datapoints.set_return_type`
# as a global config setting for the whole program, or as a context manager
# (read its docs to learn more about caveats):

with datapoints.set_return_type("datapoint"):
    new_bboxes = bboxes + 3
assert isinstance(new_bboxes, datapoints.BoundingBoxes)

# %%
# Why is this happening?
# ^^^^^^^^^^^^^^^^^^^^^^
#
# **For performance reasons**. :class:`~torchvision.datapoints.Datapoint`
# classes are Tensor subclasses, so any operation involving a
# :class:`~torchvision.datapoints.Datapoint` object will go through the
# `__torch_function__
# <https://pytorch.org/docs/stable/notes/extending.html#extending-torch>`_
# protocol. This induces a small overhead, which we want to avoid when possible.
# This doesn't matter for built-in ``torchvision`` transforms because we can
# avoid the overhead there, but it could be a problem in your model's
# ``forward``.
#
# **The alternative isn't much better anyway.** For every operation where
# preserving the :class:`~torchvision.datapoints.Datapoint` type makes
# sense, there are just as many operations where returning a pure Tensor is
# preferable: for example, is ``img.sum()`` still an :class:`~torchvision.datapoints.Image`?
# If we were to preserve :class:`~torchvision.datapoints.Datapoint` types all
# the way, even model's logits or the output of the loss function would end up
# being of type :class:`~torchvision.datapoints.Image`, and surely that's not
# desirable.
#
# .. note::
#
#    This behaviour is something we're actively seeking feedback on. If you find this surprising or if you
#    have any suggestions on how to better support your use-cases, please reach out to us via this issue:
#    https://github.com/pytorch/vision/issues/7319
#
# Exceptions
# ^^^^^^^^^^
#
# There are a few exceptions to this "unwrapping" rule:
# :meth:`~torch.Tensor.clone`, :meth:`~torch.Tensor.to`,
# :meth:`torch.Tensor.detach`, and :meth:`~torch.Tensor.requires_grad_` retain
# the datapoint type.
#
# Inplace operations on datapoints like ``obj.add_()`` will preserve the type of
# ``obj``. However, the **returned** value of inplace operations will be a pure
# tensor:

image = datapoints.Image([[[0, 1], [1, 0]]])

new_image = image.add_(1).mul_(2)

# image got transformed in-place and is still an Image datapoint, but new_image
# is a Tensor. They share the same underlying data and they're equal, just
# different classes.
assert isinstance(image, datapoints.Image)
print(image)

assert isinstance(new_image, torch.Tensor) and not isinstance(new_image, datapoints.Image)
assert (new_image == image).all()
assert new_image.data_ptr() == image.data_ptr()
