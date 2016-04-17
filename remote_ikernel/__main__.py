"""
Remote IKernel entry point.

From here you can get to 'manage', otherwise it is assumed
that a kernel is required instead and instance one instead.
"""

import sys


def main():
    """Enter into remote_ikernel."""
    if 'manage' in sys.argv:
        from remote_ikernel.manage import manage
        manage()
    else:
        from remote_ikernel.kernel import start_remote_kernel
        start_remote_kernel()


if __name__ == "__main__":
    main()
