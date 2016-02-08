#!/usr/bin/env python

"""
kernel.py

Run standard IPython/Jupyter kernels on remote machines using
job schedulers.

"""

import argparse
import json
import logging
import os
import re
import subprocess
import time

import pexpect

from tornado.log import LogFormatter

from remote_ikernel import RIK_PREFIX, __version__

# Where remote system has a different filesystem, a temporary file is needed
# to hold the json.
TEMP_KERNEL_NAME = './{0}kernel.json'.format(RIK_PREFIX)
# ALl the ports that need to be forwarded
PORT_NAMES = ['hb_port', 'shell_port', 'iopub_port', 'stdin_port',
              'control_port']

# Blend in with the notebook logging
_LOG_FMT = ("%(color)s[%(levelname)1.1s %(asctime)s.%(msecs).03d "
            "%(name)s]%(end_color)s %(message)s")
_LOG_DATEFMT = "%H:%M:%S"


def _setup_logging(verbose):
    """
    Create a logger using tornado coloured output to appear like
    notebook messages. Will clear any existing handlers too.
    """

    log = logging.getLogger('remote_ikernel')
    if verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
    # Logging on stderr
    console = logging.StreamHandler()
    console.setFormatter(LogFormatter(fmt=_LOG_FMT, datefmt=_LOG_DATEFMT))

    log.handlers = []
    log.addHandler(console)

    # So that we can attach these to pexpect for debugging purposes
    # we need to make them look like files
    def _write(*args, **_):
        """
        Method to attach to a logger to allow it to act like a file object.

        """
        message = args[0]
        # convert bytes from pexpect to something that prints better
        if hasattr(message, 'decode'):
            message = message.decode('utf-8')

        for line in message.splitlines():
            if line.strip():
                log.debug(line)

    def _pass():
        """pass"""
        pass

    log.write = _write
    log.flush = _pass

    return log


def get_password(prompt):
    """
    Interact with the user and ask for a password.

    Parameters
    ----------
    prompt : str
        Text to show the user when asking for a password.

    Returns
    -------
    password : str
        The text input by the user.

    """

    if 'SSH_ASKPASS' in os.environ:
        password = subprocess.check_output([os.environ['SSH_ASKPASS'],
                                            prompt])
    else:
        raise RuntimeError("Unable to get password, try setting SSH_ASKPASS")

    return password


def check_password(connection):
    """
    Check to see if a newly spawned process requires a password and retrieve
    it from the user if it does. Send the password to the process and
    check repeatedly for more passwords.

    Parameters
    ----------
    connection : pexpect.spawn
        The connection to check. Requires an expect and sendline method.

    """
    # This will loop until no more passwords are encountered
    while True:
        try:
            # Return all output as soon as anything arrives.
            # Assume that immediate output includes the
            # request for a password, or goes straight to
            # a prompt.
            text = connection.read_nonblocking(99999)
        except pexpect.TIMEOUT:
            # Nothing more to read from the output
            return

        re_passphrase = re.search(b'Enter passphrase .*:', text)
        re_password = re.search(b'.*@.* password:', text)
        if re_passphrase:
            passphrase = get_password(re_passphrase.group())
            connection.sendline(passphrase)
        elif re_password:
            password = get_password(re_password.group())
            connection.sendline(password)
        else:
            # No more passwords or passphrases requested
            return


class RemoteIKernel(object):
    """
    Configurable remote IPython kernel than runs on a node on a cluster
    using the a job manager system.

    """

    def __init__(self, connection_info=None, interface='sge', cpus=1, pe='smp',
                 kernel_cmd='ipython kernel', workdir=None, tunnel=True,
                 host=None, precmd=None, launch_args=None, verbose=False,
                 tunnel_hosts=None, launch_cmd=None):
        """
        Initialise a kernel on a remote machine and start tunnels.

        """

        self.log = _setup_logging(verbose)
        self.log.info("Remote kernel version: {0}.".format(__version__))
        self.log.info("File location: {0}.".format(__file__))
        # The connection info is provided by the notebook
        self.connection_info = json.load(open(connection_info))
        self.interface = interface
        self.cpus = cpus
        self.pe = pe
        self.kernel_cmd = kernel_cmd
        self.host = host  # Name of node to be changed once connection is ready.
        self.tunnel_hosts = tunnel_hosts
        self.connection = None  # will usually be a spawned pexpect
        self.workdir = workdir
        self.tunnel = tunnel
        self.tunnels = {}  # Processes running the SSH tunnels
        self.precmd = precmd
        self.launch_cmd = launch_cmd
        self.launch_args = launch_args
        self.cwd = os.getcwd()  # Launch directory may be needed if no workdir

        # Initiate an ssh tunnel through any tunnel hosts
        # this will start a pexpect, so we must check if
        # self.connection exists when launching the interface
        if self.tunnel_hosts is not None:
            self.launch_tunnel_hosts()

        if self.interface == 'local':
            self.launch_local()
        elif self.interface == 'pbs':
            self.launch_pbs()
        elif self.interface == 'sge':
            self.launch_sge()
        elif self.interface == 'sge_qrsh':
            self.launch_sge(qlogin='qrsh')
        elif self.interface == 'slurm':
            self.launch_slurm()
        elif self.interface == 'lsf':
            self.launch_lsf()
        elif self.interface == 'ssh':
            self.launch_ssh()
        else:
            raise ValueError("Unknown interface {0}".format(interface))

        # If we've established a connection, start the kernel!
        if self.connection is not None:
            self.start_kernel()
            if self.tunnel:
                self.tunnel_connection()

    def get_cmd(self, default):
        """
        Check if cmd has been overridden and return that, otherwise use the
        default.
        """
        if self.launch_cmd is not None:
            self.log.info("Overriding default '{0}' with '{1}'.".format(
                    default, self.launch_cmd))
            return self.launch_cmd
        else:
            self.log.info("Default launch command: '{0}'.".format(default))
            return default

    def launch_tunnel_hosts(self):
        """
        Build a chain of hosts to tunnel through and start an ssh
        chain with pexpect.
        """
        # TODO: does this need to be more than several ssh commands?
        self._spawn(self.tunnel_hosts_cmd)
        check_password(self.connection)

    def launch_local(self):
        """
        Initialise a shell on the local machine that can be interacted with.
        Stop tunneling if it is not needed.
        """
        self.log.info("Launching local kernel.")
        if self.launch_args:
            bash = '{bash} {args}'.format(bash=self.get_cmd('/bin/bash'),
                                          args=self.launch_args)
        else:
            bash = self.get_cmd('/bin/bash')
        self._spawn(bash)
        # Don't try and start tunnels to the same machine. Causes issues.
        self.tunnel = False

    def launch_ssh(self):
        """
        Initialise a connection through ssh.

        Launch an ssh connection using pexpect so it can be interacted with.
        """
        self.log.info("Launching kernel over SSH.")
        if self.launch_args:
            launch_args = self.launch_args
        else:
            launch_args = ''
        login_cmd = 'ssh -o StrictHostKeyChecking=no {args} {host}'.format(
            args=launch_args, host=self.host)
        self.log.info("Login command: '{0}'.".format(login_cmd))
        self._spawn(login_cmd)
        check_password(self.connection)

    def launch_pbs(self):
        """
        Start a kernel through the torque 'qsub -I' command. The connection
        will use the object's connection_info and kernel_command.
        """
        self.log.info("Launching kernel through PBS/Torque.")
        job_name = 'remote_ikernel'
        if self.cpus > 1:
            cpu_string = "-l ncpus={cpus}".format(cpus=self.cpus)
        else:
            cpu_string = ''
        if self.launch_args:
            args_string = self.launch_args
        else:
            args_string = ''
        pbs_cmd = '{qsub} -I {cpus} -N {name} {args}'.format(
                cpus=cpu_string, name=job_name, args=args_string,
                qsub=self.get_cmd('qsub'))
        self.log.info("PBS command: '{0}'.".format(pbs_cmd))
        # Will wait in the queue for up to 10 mins
        qsub_i = self._spawn(pbs_cmd)
        # Hopefully this text is universal? Job started...
        qsub_i.expect('qsub: job (.*) ready')
        # Now we have to ask for the hostname (any way for it to
        # say automatically?)
        qsub_i.sendline('echo Running on `hostname`')

        # hostnames whould be alphanumeric with . and - permitted
        # This way we also ignore the echoed echo command
        qsub_i.expect('Running on ([\w.-]+)')
        node = qsub_i.match.groups()[0]

        self.log.info("Established session on node: {0}.".format(node))
        self.host = node

    def launch_sge(self, qlogin='qlogin'):
        """
        Start a kernel through the gridengine 'qlogin' command. The connection
        will use the object's connection_info and kernel_command. 'qlogin' can
        also be replaced with 'qrsh' on some systems.
        """
        self.log.info("Launching kernel through GridEngine.")
        job_name = 'remote_ikernel'
        if self.cpus > 1:
            pe_string = "-pe {pe} {cpus}".format(pe=self.pe, cpus=self.cpus)
        else:
            pe_string = ''
        if self.launch_args:
            args_string = self.launch_args
        else:
            args_string = ''
        sge_cmd = '{qlogin} -verbose -now n {pe} -N {name} {args}'.format(
                qlogin=self.get_cmd(qlogin), pe=pe_string, name=job_name,
                args=args_string)
        self.log.info("Gridengine command: '{0}'.".format(sge_cmd))
        # Will wait in the queue for up to 10 mins
        qlogin = self._spawn(sge_cmd)
        # Hopefully this text is universal?
        qlogin.expect('Establishing .* session to host (.*) ...')

        node = qlogin.match.groups()[0]
        self.log.info("Established session on node: {0}.".format(node))
        self.host = node

    def launch_slurm(self):
        """
        Start a kernel through the slurm 'srun' command. Bind the spawned
        pexpect to the class to interact with it.
        """
        self.log.info("Launching kernel through SLURM.")
        job_name = 'remote_ikernel'
        if self.cpus > 1:
            tasks = "--cpus-per-task {cpus}".format(cpus=self.cpus)
        else:
            tasks = ""
        if self.launch_args:
            launch_args = self.launch_args
        else:
            launch_args = ''
        # -u disables buffering, -i is interactive, -v so we know the node
        # tasks must be before the bash!
        srun_cmd = '{srun}  {tasks} -J {job_name} {args} -v -u bash -i'.format(
            srun=self.get_cmd('srun'), tasks=tasks, job_name=job_name,
            args=launch_args)
        self.log.info("SLURM command: '{0}'.".format(srun_cmd))
        srun = self._spawn(srun_cmd)
        # Hopefully this text is universal?
        srun.expect('srun: Node (.*), .* tasks started')

        node = srun.match.groups()[0]
        self.log.info("Established session on node: {0}.".format(node))
        self.host = node

    def launch_lsf(self):
        """
        Start a kernel through the Platform LSF 'bsub' command in interactive
        mode. Bind the spawned pexpect to the class to interact with it.
        """
        self.log.info("Launching kernel through Platform LSF.")
        job_name = 'remote_ikernel'
        if self.cpus > 1:
            tasks = "-n {cpus}".format(cpus=self.cpus)
        else:
            tasks = ""
        if self.launch_args:
            launch_args = self.launch_args
        else:
            launch_args = ''
        # -Is is interactive shell mode
        bsub_cmd = '{bsub} -Is /bin/bash {tasks} -J {job_name} {args}'.format(
            bsub=self.get_cmd('bsub'), tasks=tasks, job_name=job_name,
            args=launch_args)
        self.log.info("LSF command: '{0}'.".format(bsub_cmd))
        bsub = self._spawn(bsub_cmd)
        # Hopefully this text is universal?
        bsub.expect('<<Starting on (.*)>>')

        node = bsub.match.groups()[0]
        self.log.info("Established session on node: {0}.".format(node))
        self.host = node

    def start_kernel(self):
        """
        Start the kernel on the remote machine.
        """
        conn = self.connection
        self.log.info("Established connection; starting kernel.")

        # Use the specified working directory or try to change to the same
        # directory on the remote machine.
        if self.workdir:
            self.log.info("Remote working directory {0}.".format(self.workdir))
            conn.sendline('cd {0}'.format(self.workdir))
        else:
            self.log.info("Current working directory {0}.".format(self.cwd))
            conn.sendline('cd {0}'.format(self.cwd))

        # Create a temporary file to store a copy of the connection information
        # Delete the file if it already exists
        conn.sendline('rm -f {0}'.format(TEMP_KERNEL_NAME))
        file_contents = json.dumps(self.connection_info)
        conn.sendline('echo \'{0}\' > {1}'.format(file_contents,
                                                  TEMP_KERNEL_NAME))

        # Is this the best place for a pre-command? I guess people will just
        # have to deal with it. Pass it on as is.
        if self.precmd:
            conn.sendline(self.precmd)

        # Init as a background process so we can delete the tempfile after
        kernel_init = '{kernel_cmd}'.format(kernel_cmd=self.kernel_cmd)
        kernel_init = kernel_init.format(host_connection_file=TEMP_KERNEL_NAME,
                                         ci=self.connection_info)
        self.log.info("Running kernel command: '{0}'.".format(kernel_init))
        conn.sendline(kernel_init)

        # The kernel blocks further commands, so queue deletion of the
        # transient file for once the process stops. Trying to do this
        # whilst simultaneously starting the kernel ended up deleting
        # the file before it was read.
        conn.sendline('rm -f {0}'.format(TEMP_KERNEL_NAME))
        conn.sendline('exit')

        # Could check this for errors?
        conn.expect('exit')

    def tunnel_connection(self):
        """
        Set up tunnels to the node using the connection information.
        """
        # Auto accept ssh keys so tunnels work on previously unknown hosts.
        # This might need to change, but the other option is to get user or
        # admin to turn StrictHostKeyChecking off in .ssh/ssh_config for this
        # to work seamlessly. (tunnels will have already done this)
        pre = self.tunnel_hosts_cmd or ''
        pexpect.spawn('{pre} ssh -o StrictHostKeyChecking=no '
                      '{host}'.format(pre=pre, host=self.host).strip()).sendline('exit')

        # connection info should have the ports being used
        tunnel_command = self.tunnel_cmd.format(**self.connection_info)
        tunnel = pexpect.spawn(tunnel_command)
        check_password(tunnel)

        self.log.info("Setting up tunnels on ports: {0}.".format(
            ", ".join(["{0}".format(self.connection_info[port_name])
                       for port_name in PORT_NAMES])))
        self.log.debug("Tunnel command: {0}.".format(tunnel_command))

        # Store the tunnel
        self.tunnels['tunnel'] = tunnel

    def check_tunnels(self):
        """
        Check the PID of tunnels and restart any that have died.
        """
        if 'tunnel' in self.tunnels:
            if not self.tunnels['tunnel'].isalive():
                self.log.debug("Restarting ssh tunnels.")
                self.tunnel_connection()

    def keep_alive(self, timeout=5):
        """
        Keep the script alive forever. KeyboardInterrupt will get passed on
        to the kernel. The timeout determines how often the ssh tunnels are
        checked.
        """
        # The timeout determines how long each loop will be,
        # if an ssh tunnel dies, this is how long it will be
        # before it is revived.
        self.connection.timeout = timeout
        time.sleep(timeout)

        # There might be a more elegant way to do this, but since this
        # process doesn't do anything and is managed by the notebook
        # it really doesn't matter
        while True:
            # If the kernel dies, we should too, but try and
            # give some error info
            if not self.connection.isalive():
                self.log.error("Kernel died.")
                for line in self.connection.readlines():
                    if line.strip():
                        self.log.error(line)
                break
            # Kernel is still alive, ensure tunnels are too
            self.check_tunnels()
            try:
                # read anything from the kernel output, pexpect
                # logging will be set up to emit anything if
                # required.
                self.connection.readlines()
            except pexpect.TIMEOUT:
                # Raises timeout if there is no data, prevents blocking
                # Moves on to the next loop.
                pass
            except KeyboardInterrupt:
                self.log.info("Caught interrupt; sending to kernel.")
                self.connection.sendcontrol('c')

    def _spawn(self, command, timeout=600):
        """
        Helper to start a pexpect.spawn as self.connection. If the session
        has already been started, just pass the command to sendline. Return
        the current spawn instance. The logfile is implicitly set to
        self.log.

        Parameters
        ----------
        command : str
            Command to spawn or run in the current session.
        timeout : int
            Timeout for command to complete, passed to pexpect.

        Returns
        -------
        connection : pexpect.spawn
            The connection object. This is also attached to the class.
        """
        if self.connection is None:
            self.connection = pexpect.spawn(command, timeout=timeout,
                                            logfile=self.log)
        else:
            self.connection.sendline(command)

        return self.connection

    @property
    def tunnel_hosts_cmd(self):
        """Return the ssh command to tunnel through the middle hosts."""
        if self.tunnel_hosts is None:
            return None

        cmd = []

        for host in self.tunnel_hosts:
            if ':' in host:
                host, port = host.split(":")
                ssh = 'ssh -o StrictHostKeyChecking=no -p {0}'.format(port)
            else:
                ssh = 'ssh -o StrictHostKeyChecking=no'

            cmd.extend([ssh, host])

        return " ".join(cmd)

    @property
    def tunnel_cmd(self):
        """Return a tunnelling command that just needs a port."""
        # zmq needs str in Python 3, but pexpect gives bytes
        if hasattr(self.host, 'decode'):
            self.host = self.host.decode('utf-8')

        # One connection can tunnel all the ports
        ports_str = " ".join(["-L 127.0.0.1:{{{port}}}:127.0.0.1:{{{port}}}"
                               "".format(port=port) for port in PORT_NAMES])

        # Add all the gateway machines as an ssh chain
        pre_ssh = []
        for pre_host in self.tunnel_hosts or []:
            if ':' in pre_host:
                # Split the host:port and insert into tunnel command
                pre_ssh.append(
                    "ssh -p {0[1]} -S none {ports_str} {0[0]}".format(
                        pre_host.split(':'), ports_str=ports_str))
            else:
                pre_ssh.append(
                    "ssh -S none {ports_str} {0}".format(
                        pre_host, ports_str=ports_str))

        if ':' in self.host:
            host, host_port = self.host.split(":")
            ssh = 'ssh -p {host_port}'.format(host_port=host_port)
        else:
            ssh = 'ssh '
            host = self.host

        # Timeout is specified here, this should be longer than the checking
        # interval
        # .strip() to prevent leading spaces
        tunnel_cmd = ((" ".join(pre_ssh) + " " +
                       "{ssh} -S none {ports_str} {host} sleep 600".format(
                           ssh=ssh, host=host, ports_str=ports_str)).strip())

        self.log.debug("Tunnel command: {0}".format(tunnel_cmd))
        return tunnel_cmd


def start_remote_kernel():
    """
    Read command line arguments and initialise a kernel.
    """
    # These will not face a user since they are interpreting the command from
    # kernel the kernel.json
    description = "This is the kernel launcher! Try '%(prog)s manage'..."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('connection_info')
    parser.add_argument('--interface', default='local')
    parser.add_argument('--cpus', type=int, default=1)
    parser.add_argument('--pe', default='smp')
    parser.add_argument('--kernel_cmd',
                        default='ipython kernel -f {host_connection_file}')
    parser.add_argument('--workdir')
    parser.add_argument('--host')
    parser.add_argument('--precmd')
    parser.add_argument('--launch-args')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--tunnel-hosts', nargs='+')
    parser.add_argument('--launch-cmd')
    parser.add_argument('--version', '-V', action='version', version="Remote "
                        "Jupyter kernel launcher (version {0}).\n\n"
                        "Use the '%(prog)s manage' subcommand for managing "
                        "kernels.".format(__version__))
    args = parser.parse_args()

    kernel = RemoteIKernel(connection_info=args.connection_info,
                           interface=args.interface, cpus=args.cpus, pe=args.pe,
                           kernel_cmd=args.kernel_cmd, workdir=args.workdir,
                           host=args.host, precmd=args.precmd,
                           launch_args=args.launch_args, verbose=args.verbose,
                           tunnel_hosts=args.tunnel_hosts,
                           launch_cmd=args.launch_cmd)
    kernel.keep_alive()
