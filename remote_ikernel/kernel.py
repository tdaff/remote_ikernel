#!/usr/bin/env python

"""

Run standard IPython/Jupyter kernels on remote machines using
job schedulers.

"""

import argparse
import json
import os
import time

import pexpect

from zmq.ssh.tunnel import ssh_tunnel

# ALl the ports that need to be forwarded
PORT_NAMES = ['hb_port', 'shell_port', 'iopub_port', 'stdin_port',
              'control_port']


class RemoteIKernel(object):
    """
    Configurable remote IPython kernel than runs on a node on a cluster
    using the a job manager system.

    """

    def __init__(self, connection_info=None, interface='sge', cpus=1, pe='smp',
                 kernel_cmd='ipython kernel', tunnel=True):
        """
        Initialise a kernel on a remote machine and start tunnels.

        """

        # The connection info is provided by the notebook
        self.connection_info = json.load(open(connection_info))
        self.interface = interface
        self.cpus = cpus
        self.pe = pe
        self.kernel_cmd = kernel_cmd
        self.node = ''  # Name of node to be changed once connection is ready.
        self.connection = None  # will usually be a spawned pexpect

        if self.interface == 'sge':
            self.launch_sge()
        else:
            raise ValueError("Unknown interface {0}".format(interface))

        if self.connection is not None and tunnel:
            self.tunnel_connection()

    def launch_sge(self):
        """
        Start a kernel through the gridengine qlogin command. The connection
        will use the object's connection_info and kernel_command.
        """
        # We have to keep track of the directory where we are spawned
        # since qlogin can't take thw cwd option.
        cwd = os.getcwd()
        if self.cpus > 1:
            pe_string = "-pe {pe} {cpus}".format(pe=self.pe, cpus=self.cpus)
        else:
            pe_string = ''
        # To debug add logfile=sys.stdout
        qlogin = pexpect.spawn('qlogin -now n {0}'.format(pe_string),
                               timeout=600)
        # Hopefully this text is universal?
        qlogin.expect('Establishing builtin session to host (.*) ...')

        node = qlogin.match.groups()[0]
        self.node = node

        qlogin.sendline('cd {0}'.format(cwd))
        qlogin.sendline('{kernel_cmd} --ip="*" '
                        '--hb={ci[hb_port]} --shell={ci[shell_port]} '
                        '--iopub={ci[iopub_port]} --stdin={ci[stdin_port]} '
                        '--control={ci[control_port]} --Session.key={ci[key]}'
                        ''.format(kernel_cmd=self.kernel_cmd,
                                  ci=self.connection_info))

        # Could check this for errors?
        qlogin.expect('.*')

        # Child process is available to the class. Keeps it referenced
        self.connection = qlogin

    def tunnel_connection(self):
        """
        Set up tunnels to the node using the connection information.
        """
        # Auto accept ssh keys so tunnels work on previously unknown hosts.
        # This might need to change, but the other option is to get user or
        # admin to turn StrictHostKeyChecking off in .ssh/ssh_config for this
        # to work seamlessly.
        pexpect.spawn('ssh -o StrictHostKeyChecking=no '
                      '{node}'.format(node=self.node)).sendline('exit')
        # Use zmq's convenience tunnel setup
        for port_name in PORT_NAMES:
            port = self.connection_info[port_name]
            ssh_tunnel(port, port, self.node, '*')

    def keep_alive(self):
        """
        Keep the script alive forever. KeyboardInterrupt will get passed on
        to the kernel.
        """

        # There might be a more elegant way to do this, but since this
        # process doesn't do anything and is managed by the notebook
        # it really doesn't matter
        while True:
            try:
                time.sleep(60)
            except KeyboardInterrupt:
                self.connection.sendcontrol('c')


def start_remote_kernel():
    """
    Read command line arguments and initialise a kernel.
    """
    # These will not face a user since they are interpreting the command from
    # kernel the kernel.json
    parser = argparse.ArgumentParser()
    parser.add_argument('connection_info')
    parser.add_argument('--interface', default='sge')
    parser.add_argument('--cpus', type=int, default=1)
    parser.add_argument('--pe', default='smp')
    parser.add_argument('--kernel_cmd', default='ipython kernel')
    args = parser.parse_args()

    kernel = RemoteIKernel(connection_info=args.connection_info,
                           interface=args.interface, cpus=args.cpus, pe=args.pe,
                           kernel_cmd=args.kernel_cmd)
    kernel.keep_alive()
