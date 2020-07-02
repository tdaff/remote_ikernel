"""
compat.py

Compatibility layer for transitions from IPython 3.0 to
Jupyter structure. Will attempt to import Jupyter versions
of modules, but will fall back to IPython if it is not
available.

Provides the following modules:
    kernelspec -> {jupyter_client,IPython}.kernel.kernelspec
    tempdir    -> {tempfile,IPython.utils.tempdir}

"""
# This is a module copied from Python 3.2, so will exist
# in 3.2 onwards
import tempfile as tempdir

# kernelspec is moved in jupyter
try:
    from jupyter_client import kernelspec
except ImportError:
    from IPython.kernel import kernelspec

# Otherwise it might be in genutils, but that will be dissolved
if not hasattr(tempdir, "TemporaryDirectory"):
    try:
        from ipython_genutils import tempdir
    except ImportError:
        from IPython.utils import tempdir

__all__ = ("kernelspec", "tempdir")
