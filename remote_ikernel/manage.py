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

# How we identify kernels that rik will manage
from remote_ikernel import RIK_PREFIX

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


def show_kernel(kernel_name):
    """
    Print the contents of the kernel.json to the terminal, plus some extra
    information.

    Parameters
    ----------
    kernel_name : str
        The name of the kernel to show the information for.
    """
    # Load the raw json, since we store some unexpected data in there too
    spec = get_kernel_spec(kernel_name)
    with open(path.join(spec.resource_dir, 'kernel.json')) as kernel_file:
        kernel_json = json.load(kernel_file)

    # Manually format the json to put each key: value on a single line
    print("Kernel found in :{0}".format(spec.resource_dir))
    print("kernel_json = {0}".format(json.dumps(kernel_json)))


def add_kernel(interface, name, kernel_cmd, cpus=1, pe=None, language=None,
               system=False, workdir=None, host=None):
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
    elif interface == 'ssh':
        if host is None:
            raise KeyError('A host is required for ssh.')
        argv.extend(['--interface', 'ssh'])
        argv.extend(['--host', host])
        kernel_name.append('ssh')
        kernel_name.append(host)
        display_name.append("SSH")
        display_name.append(host)
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

    if workdir is not None:
         argv.extend(['--workdir', workdir])

    # protect the {connection_file} part of the kernel command
    kernel_cmd = kernel_cmd.replace('{connection_file}',
                                    '{host_connection_file}')
    argv.extend(['--kernel_cmd', kernel_cmd])

    # remote_ikernel needs the connection file too
    argv.append('{connection_file}')

    # Prefix all kernels with 'remote_' for management.
    kernel_name = RIK_PREFIX + '-'.join(kernel_name)
    kernel_json = {
        'display_name': " ".join(display_name),
        'argv': argv,
    }

    if language is not None:
        kernel_json['language'] = language

    # Put the commandline in so that '--show' will show how to recreate
    # the kernel
    kernel_json['remote_ikernel_argv'] = sys.argv

    # False attempts a system install, otherwise install as the current user
    if system:
        username = False
    else:
        username = getpass.getuser()

    # kernel.json file installation
    with TemporaryDirectory() as temp_dir:
        os.chmod(temp_dir, 0o755)  # Starts off as 700, not user readable

        with open(path.join(temp_dir, 'kernel.json'), 'w') as kernel_file:
            json.dump(kernel_json, kernel_file, sort_keys=True, indent=2)

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
        if kernel_name.startswith(RIK_PREFIX):
            spec = get_kernel_spec(kernel_name)
            display = "  ['{kernel_name}']: {desc}".format(
                kernel_name=kernel_name, desc=spec.display_name)
            existing_kernels[kernel_name] = spec
            description.append(display)

    # The raw formatter stops lines wrapping
    parser = argparse.ArgumentParser(
        prog='%prog manage', description="\n".join(description),
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--show', '-s', help="Print the contents of the "
                        "kernel.")
    parser.add_argument('--add', '-a', action="store_true", help="Add a new "
                        "kernel according to other commandline options.")
    parser.add_argument('--delete', '-d', help="Remove the kernel and delete "
                        "the associated kernel.json.")
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
    parser.add_argument('--host', '-x', help="The hostname or ip address "
                        "running through an SSH connection.")
    parser.add_argument('--interface', '-i', choices=['sge', 'ssh'],
                        help="Specify how the remote kernel is launched.")
    parser.add_argument('--system', help="Install the kernel into the system "
                        "directory so that it is available for all users. "
                        "Might need admin privilidges.", action='store_true')
    parser.add_argument('--workdir', help="Directory in which to start the "
                        "kernel. If not specified it will use the current "
                        "directory. This is important if the local and remote "
                        "filesystems differ.")

    # Temporarily remove 'manage' from the arguments
    raw_args = sys.argv[:]
    sys.argv.remove('manage')
    args = parser.parse_args()
    sys.argv = raw_args

    if args.add:
        kernel_name = add_kernel(args.interface, args.name, args.kernel_cmd,
                                 args.cpus, args.pe, args.language, args.system,
                                 args.workdir, args.host)
        print("Installed kernel {0}.".format(kernel_name))
    elif args.delete:
        if args.delete in existing_kernels:
            delete_kernel(args.delete)
        else:
            print("Can't delete {0}".format(args.delete))
            print("\n".join(description[2:]))
    elif args.show:
        if args.show in existing_kernels:
            show_kernel(args.show)
        else:
            print("Kernel {0} doesn't exist".format(args.show))
            print("\n".join(description[2:]))
    else:
        parser.print_help()
