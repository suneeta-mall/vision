import functools
from typing import Any, Callable, Dict, List, Optional, Sequence, Type, Union

import torch
from torchvision import datapoints

_FillType = Union[int, float, Sequence[int], Sequence[float], None]
_FillTypeJIT = Optional[List[float]]


def is_pure_tensor(inpt: Any) -> bool:
    return isinstance(inpt, torch.Tensor) and not isinstance(inpt, datapoints.Datapoint)


# {functional: {input_type: type_specific_kernel}}
_KERNEL_REGISTRY: Dict[Callable, Dict[Type, Callable]] = {}


def _kernel_datapoint_wrapper(kernel):
    @functools.wraps(kernel)
    def wrapper(inpt, *args, **kwargs):
        # If you're wondering whether we could / should get rid of this wrapper,
        # the answer is no: we want to pass pure Tensors to avoid the overhead
        # of the __torch_function__ machinery. Note that this is always valid,
        # regardless of whether we override __torch_function__ in our base class
        # or not.
        # Also, even if we didn't call `as_subclass` here, we would still need
        # this wrapper to call wrap(), because the Datapoint type would be
        # lost after the first operation due to our own __torch_function__
        # logic.
        output = kernel(inpt.as_subclass(torch.Tensor), *args, **kwargs)
        return datapoints.wrap(output, like=inpt)

    return wrapper


def _register_kernel_internal(functional, input_type, *, datapoint_wrapper=True):
    registry = _KERNEL_REGISTRY.setdefault(functional, {})
    if input_type in registry:
        raise ValueError(f"Functional {functional} already has a kernel registered for type {input_type}.")

    def decorator(kernel):
        registry[input_type] = (
            _kernel_datapoint_wrapper(kernel)
            if issubclass(input_type, datapoints.Datapoint) and datapoint_wrapper
            else kernel
        )
        return kernel

    return decorator


def _name_to_functional(name):
    import torchvision.transforms.v2.functional  # noqa

    try:
        return getattr(torchvision.transforms.v2.functional, name)
    except AttributeError:
        raise ValueError(
            f"Could not find functional with name '{name}' in torchvision.transforms.v2.functional."
        ) from None


_BUILTIN_DATAPOINT_TYPES = {
    obj for obj in datapoints.__dict__.values() if isinstance(obj, type) and issubclass(obj, datapoints.Datapoint)
}


def register_kernel(functional, datapoint_cls):
    """[BETA] Decorate a kernel to register it for a functional and a (custom) datapoint type.

    See :ref:`sphx_glr_auto_examples_transforms_plot_custom_datapoints.py` for usage
    details.
    """
    if isinstance(functional, str):
        functional = _name_to_functional(name=functional)
    elif not (
        callable(functional)
        and getattr(functional, "__module__", "").startswith("torchvision.transforms.v2.functional")
    ):
        raise ValueError(
            f"Kernels can only be registered on functionals from the torchvision.transforms.v2.functional namespace, "
            f"but got {functional}."
        )

    if not (isinstance(datapoint_cls, type) and issubclass(datapoint_cls, datapoints.Datapoint)):
        raise ValueError(
            f"Kernels can only be registered for subclasses of torchvision.datapoints.Datapoint, "
            f"but got {datapoint_cls}."
        )

    if datapoint_cls in _BUILTIN_DATAPOINT_TYPES:
        raise ValueError(f"Kernels cannot be registered for the builtin datapoint classes, but got {datapoint_cls}")

    return _register_kernel_internal(functional, datapoint_cls, datapoint_wrapper=False)


def _get_kernel(functional, input_type, *, allow_passthrough=False):
    registry = _KERNEL_REGISTRY.get(functional)
    if not registry:
        raise ValueError(f"No kernel registered for functional {functional.__name__}.")

    for cls in input_type.__mro__:
        if cls in registry:
            return registry[cls]
        elif cls is datapoints.Datapoint:
            # We don't want user-defined datapoints to dispatch to the pure Tensor kernels, so we explicit stop the
            # MRO traversal before hitting torch.Tensor. We can even stop at datapoints.Datapoint, since we don't
            # allow kernels to be registered for datapoints.Datapoint anyway.
            break

    if allow_passthrough:
        return lambda inpt, *args, **kwargs: inpt

    raise TypeError(
        f"Functional F.{functional.__name__} supports inputs of type {registry.keys()}, "
        f"but got {input_type} instead."
    )


# This basically replicates _register_kernel_internal, but with a specialized wrapper for five_crop / ten_crop
# We could get rid of this by letting _register_kernel_internal take arbitrary functionals rather than wrap_kernel: bool
def _register_five_ten_crop_kernel_internal(functional, input_type):
    registry = _KERNEL_REGISTRY.setdefault(functional, {})
    if input_type in registry:
        raise TypeError(f"Functional '{functional}' already has a kernel registered for type '{input_type}'.")

    def wrap(kernel):
        @functools.wraps(kernel)
        def wrapper(inpt, *args, **kwargs):
            output = kernel(inpt, *args, **kwargs)
            container_type = type(output)
            return container_type(datapoints.wrap(o, like=inpt) for o in output)

        return wrapper

    def decorator(kernel):
        registry[input_type] = wrap(kernel) if issubclass(input_type, datapoints.Datapoint) else kernel
        return kernel

    return decorator
