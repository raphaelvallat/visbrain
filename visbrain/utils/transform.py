"""This script contains some other utility functions."""
import numpy as np
from vispy.visuals.transforms import (STTransform, ChainTransform)


__all__ = ('vprescale', 'vprecenter', 'vpnormalize')


def vprescale(obj, dist=1.):
    """Get the vispy transformation for rescaling objects.

    Parameters
    ----------
    obj : tuple
        The ndarray of the object to rescale. Must be a (..., 2) or (..., 3).
    dist : float | 1.
        The final rescaling value.

    Returns
    -------
    rescale : vispy.transformations
        VisPy transformation to rescale.
    """
    # Get minimum / maximum trough last dimension :
    dim = tuple(np.arange(obj.ndim - 1, dtype=int))
    ptp = np.max(obj, axis=dim) - np.min(obj, axis=dim)
    return STTransform(scale=[dist / np.max(ptp)] * 3)


def vprecenter(obj):
    """Get the vispy transformation to recenter objects.

    Parameters
    ----------
    obj : tuple
        The ndarray of the object to recenter. Must be a (..., 2) or (..., 3).

    Returns
    -------
    recenter : vispy.transformations
        VisPy transformation to recenter.
    """
    # Check object :
    if not isinstance(obj, np.ndarray) or obj.shape[-1] not in [2, 3]:
        raise ValueError("The object must be a ndarray of shape (..., 2) or "
                         "(..., 3)")
    # Get center :
    center = np.mean(obj, axis=tuple(np.arange(obj.ndim - 1, dtype=int)))
    if center.shape[-1] == 2:
        center = np.hstack((center, 0.))
    # Build transformation :
    return STTransform(translate=-center)


def vpnormalize(obj, dist=1.):
    """Get the vispy transformation for normalizing objects.

    Parameters
    ----------
    obj : tuple
        The ndarray of the object to rescale. Must be a (..., 2) or (..., 3).
    dist : float | 1.
        The final rescaling value.

    Returns
    -------
    normalize : vispy.transformations
        VisPy transformation to normalize.
    """
    # Prepare the transformation chain :
    t = ChainTransform()
    # Recenter the object :
    t.prepend(vprecenter(obj))
    # Rescale :
    t.prepend(vprescale(obj, dist))
    return t
