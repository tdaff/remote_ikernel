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

from remote_ikernel import RIK_PREFIX

# Where remote system has a different filesystem, a temporary file is needed
# to hold the json.
TEMP_KERNEL_NAME = './{0}kernel.json'.format(RIK_PREFIX)
# ALl the ports that need to be forwarded
PORT_NAMES = ['hb_port', 'shell_port', 'iopub_port', 'stdin_port',
              'control_port']


class RemoteIKernel(object):
    """
    Configurable remote IPython kernel than runs on a node on a cluster
    using the a job manager system.

    """

    def __init__(self, connection_info=None, interface='sge', cpus=1, pe='smp',
                 kernel_cmd='ipython kernel', workdir=None, tunnel=True,
                 host=None):
        """
        Initialise a kernel on a remote machine and start tunnels.

        """

        # The connection info is provided by the notebook
        self.connection_info = json.load(open(connection_info))
        self.interface = interface
        self.cpus = cpus
        self.pe = pe
        self.kernel_cmd = kernel_cmd
        self.host = host  # Name of node to be changed once connection is ready.
        self.connection = None  # will usually be a spawned pexpect
        self.workdir = workdir
        self.tunnel = tunnel
        self.cwd = os.getcwd()  # Launch directory may be needed if no workdir

        if self.interface == 'local':
            self.launch_local()
        elif self.interface == 'sge':
            self.launch_sge()
        elif self.interface == 'ssh':
            self.launch_ssh()
        elif self.interface == 'slurm':
            self.launch_slurm()
        else:
            raise ValueError("Unknown interface {0}".format(interface))

        # If we've established a connection, start the kernel!
        if self.connection is not None:
            self.start_kernel()
            if self.tunnel:
                self.tunnel_connection()

    def launch_local(self):
        """
        Initialise a shell on the local machine that can be interacted with.
        Stop tunneling.
        """
        self.connection = pexpect.spawn('/bin/bash')
        # Don't try and start tunnels to the same machine. Causes issues.
        self.tunnel = False

    def launch_ssh(self):
        """
        Initialise a connection through ssh.

        Launch an ssh connection using pexpect so it can be interacted with.
        """
        login = pexpect.spawn('ssh -o StrictHostKeyChecking=no '
                              '{host}'.format(host=self.host))
        self.connection = login

    def launch_sge(self):
        """
        Start a kernel through the gridengine 'qlogin' command. The connection
        will use the object's connection_info and kernel_command.
        """
        if self.cpus > 1:
            pe_string = "-pe {pe} {cpus}".format(pe=self.pe, cpus=self.cpus)
        else:
            pe_string = ''
        # To debug add logfile=sys.stdout
        # Will wait in the queue for up to 10 mins
        qlogin = pexpect.spawn('qlogin -now n {0}'.format(pe_string),
                               timeout=600)
        # Hopefully this text is universal?
        qlogin.expect('Establishing builtin session to host (.*) ...')

        node = qlogin.match.groups()[0]
        self.host = node

        # Child process is available to the class. Keeps it referenced
        self.connection = qlogin

    def launch_slurm(self):
        """
        Start a kernel through the slurm 'srun' command. Bind the spawned
        pexpect to the class to interact with it.
        """
        if self.cpus > 1:
            tasks = "--cpus-per-task {cpus}".format(cpus=self.cpus)
        else:
            tasks = ""
        # -u disables buffering, -i is interactive, -v so we know the node
        # tasks must be before the bash!
        srun = pexpect.spawn('srun  {0} -v -u bash -i'.format(tasks),
                             timeout=600)
        # Hopefully this text is universal?
        srun.expect('srun: Node (.*), .* tasks started')

        node = srun.match.groups()[0]
        self.host = node

        # Child process is available to the class. Keeps it referenced
        self.connection = srun

    def start_kernel(self):
        """
        Start the kernel on the remote machine.
        """
        conn = self.connection

        # Use the specified working directory or try to change to the same
        # directory on the remote machine.
        if self.workdir:
            conn.sendline('cd {0}'.format(self.workdir))
        else:
            conn.sendline('cd {0}'.format(self.cwd))

        # Create a temporary file to store a copy of the connection information
        # Delete the file if it already exists
        conn.sendline('rm -f {0}'.format(TEMP_KERNEL_NAME))
        file_contents = json.dumps(self.connection_info)
        conn.sendline('echo \'{0}\' > {1}'.format(file_contents,
                                                  TEMP_KERNEL_NAME))

        # Init as a background process so we can delete the tempfile after
        kernel_init = '{kernel_cmd}'.format(kernel_cmd=self.kernel_cmd)
        kernel_init = kernel_init.format(host_connection_file=TEMP_KERNEL_NAME,
                                         ci=self.connection_info)
        conn.sendline(kernel_init)

        # The kernel blocks further commands, so queue deletion of the
        # transient file for once the process stops. Trying to do this
        # whilst simultaneously starting the kernel ended up deleting
        # the file before it was read.
        conn.sendline('rm -f {0}'.format(TEMP_KERNEL_NAME))
        conn.sendline('exit')

        # Could check this for errors?
        conn.expect('.*')

    def tunnel_connection(self):
        """
        Set up tunnels to the node using the connection information.
        """
        # Auto accept ssh keys so tunnels work on previously unknown hosts.
        # This might need to change, but the other option is to get user or
        # admin to turn StrictHostKeyChecking off in .ssh/ssh_config for this
        # to work seamlessly.
        pexpect.spawn('ssh -o StrictHostKeyChecking=no '
                      '{host}'.format(host=self.host)).sendline('exit')
        # Use zmq's convenience tunnel setup
        for port_name in PORT_NAMES:
            port = self.connection_info[port_name]
            ssh_tunnel(port, port, self.host, '*')

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
    description = "This is the kernel launcher, did you mean '%prog manage'"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('connection_info')
    parser.add_argument('--interface', default='sge')
    parser.add_argument('--cpus', type=int, default=1)
    parser.add_argument('--pe', default='smp')
    parser.add_argument('--kernel_cmd', default='ipython kernel -f {host_connection_file}')
    parser.add_argument('--workdir')
    parser.add_argument('--host')
    args = parser.parse_args()

    kernel = RemoteIKernel(connection_info=args.connection_info,
                           interface=args.interface, cpus=args.cpus, pe=args.pe,
                           kernel_cmd=args.kernel_cmd, workdir=args.workdir,
                           host=args.host)
    kernel.keep_alive()
