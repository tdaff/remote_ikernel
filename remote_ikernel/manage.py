"""
manage.py

Manage the kernels available to remote_ikernel.
Run ``remote_ikernel manage`` to see a list of commands.

"""

from __future__ import print_function

import argparse
import getpass
import json
import os
import re
import sys
from os import path

from IPython.kernel.kernelspec import find_kernel_specs, get_kernel_spec
from IPython.kernel.kernelspec import install_kernel_spec
from IPython.utils.tempdir import TemporaryDirectory


def delete_kernel(kernel_name):
    """
    Delete the kernel by removing the kernel.json and directory.

    Parameters
    ----------
    kernel_name : str
        The name of the kernel to delete

    Raises
    ------
    KeyError
        If the kernel is not found.
    """
    spec = get_kernel_spec(kernel_name)
    os.remove(path.join(spec.resource_dir, 'kernel.json'))
    try:
        os.rmdir(spec.resource_dir)
    except OSError:
        # Non empty directory, just leave it
        pass


def add_kernel(interface, name, kernel_cmd, cpus=1, pe=None, language=None,
               user=False):
    """
    Add a kernel. Generates a kernel.json and installs it for the system or
    user.
    """
    kernel_name = []
    display_name = []
    argv = [sys.executable, '-m', 'remote_ikernel']

    # How to connect to kernel
    if interface == 'sge':
        argv.extend(['--interface', 'sge'])
        kernel_name.append('sge')
        display_name.append("GridEngine")
    else:
        raise ValueError("Unknown interface {0}".format(interface))

    display_name.append(name)
    kernel_name.append(re.sub(r'\W', '', name).lower())

    if pe is not None:
        argv.extend(['--pe', pe])
        kernel_name.append(pe)
        display_name.append(pe)

    if cpus > 1:
        argv.extend(['--cpus', '{0}'.format(cpus)])
        kernel_name.append('{0}'.format(cpus))
        display_name.append('{0} CPUs'.format(cpus))

    argv.extend(['--kernel_cmd', format(kernel_cmd)])

    argv.append('{connection_file}')

    # Prefix all kernels with 'remote_' for management.
    kernel_name = 'remote_' + '-'.join(kernel_name)
    kernel_json = {
        'display_name': " ".join(display_name),
        'argv': argv,
    }

    if language is not None:
        kernel_json['language'] = language

    # Install as the current user, otherwise False attempts a system install
    if user:
        username = getpass.getuser()
    else:
        username = False

    # kernel.json file installation
    with TemporaryDirectory() as temp_dir:
        os.chmod(temp_dir, 0o755)  # Starts off as 700, not user readable

        with open(os.path.join(temp_dir, 'kernel.json'), 'w') as kernel_file:
            json.dump(kernel_json, kernel_file, sort_keys=True)

        install_kernel_spec(temp_dir, kernel_name, user=username, replace=True)

    return kernel_name


def manage():
    """
    Manage the available remote_ikernels.

    All the options are pulled from arguments so we take no
    arguments here.
    """

    description = ["Remote IKernel management utility", "",
                   "Currently installed kernels:"]
    existing_kernels = {}

    # Sort so they are always in the same order
    for kernel_name in sorted(find_kernel_specs()):
        if kernel_name.startswith('remote_'):
            spec = get_kernel_spec(kernel_name)
            display = "  ['{kernel_name}']: {desc}".format(
                kernel_name=kernel_name, desc=spec.display_name)
            existing_kernels[kernel_name] = spec
            description.append(display)

    # The raw formatter stops lines wrapping
    parser = argparse.ArgumentParser(
        prog='%prog manage', description="\n".join(description),
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--add', '-a', action="store_true", help="Add a new "
                        "kernel according to other commandline options.")
    parser.add_argument('--kernel_cmd', '-k', help="Kernel command "
                        "to install.")
    parser.add_argument('--name', '-n', help="Name to identify the kernel,"
                        "e.g. 'Python 2.7'.")
    parser.add_argument('--language', '-', help="Explicitly specify the "
                        "language of the kernel.")
    parser.add_argument('--cpus', '-c', type=int, help="Launch the kernel "
                        "as a multi-core job with this many cores if > 1.")
    parser.add_argument('--pe', help="Parallel environment to use on when"
                        "running on gridengine.")
    parser.add_argument('--interface', '-i', choices=['sge'], help="Specify "
                        "how the remote kernel is launched.")
    parser.add_argument('--delete', '-d', help="Remove the kernel and delete "
                        "the associated kernel.json.")
    parser.add_argument('--user', help="Install the kernel only for the "
                        "current user.", action='store_true')

    args = parser.parse_args()

    if args.add:
        kernel_name = add_kernel(args.interface, args.name, args.kernel_cmd,
                                 args.cpus, args.pe, args.language, args.user)
        print("Installed kernel {0}.".format(kernel_name))
    elif args.delete:
        if args.delete in existing_kernels:
            delete_kernel(args.delete)
        else:
            print("Can't delete {0}".format(args.delete))
            print("\n".join(description[2:]))
    else:
        parser.print_help()
