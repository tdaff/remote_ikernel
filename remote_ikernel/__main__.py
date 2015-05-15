"""
Remote IKernel entry point.

From here you can get to 'manage', otherwise it is assumed
that a kernel is required instead and instance one instead.
"""

import sys

if 'manage' in sys.argv:
    from remote_ikernel.manage import manage
    manage()
else:
    from remote_ikernel.kernel import start_remote_kernel
    start_remote_kernel()
