Remote IKernel
--------------

All your Jupyter kernels, on all your machines, in one place.

Launch Jupyter kernels on remote systems and through batch queues so that
they can be used within a local Jupyter noteboook.

.. image :: https://bitbucket.org/tdaff/remote_ikernel/raw/default/doc/kernels.png

Jupyter compatible Kernels start through interactive jobs in batch queue
systems (SGE, SLURM, PBS...) or through SSH connections. Once the kernel is
started, SSH tunnels are created for the communication ports are so the
notebook can talk to the kernel as if it was local.

Commands for managing the kernels are included. It is also possible to use
``remote_ikernel`` to manage kernels from different virtual environments or
different python implementations.

Install with ``pip install remote_ikernel``. Requires ``notebook`` (as part
of Jupyter), version 4.0 or greater and ``pexpect``. Passwordless ``ssh``
to the all the remote machines is also recommended (e.g. nodes on a cluster).

.. warning::

   ``remote_ikernel`` opens multiple connections across several machines
   to tunnel communication ports. If you have concerns about security or
   excessive use of resources, please consult your systems administrator
   before using this software.

.. note::

   When running kernels on remote machines, the notebooks themselves will
   be saved onto the local filesystem, but the kernel will only have access
   to filesystem of the remote machine running the kernel. If you need shared
   directories, set up ``sshfs`` between your machines.


.. code:: shell

   # Install the module ('python setup.py install' also works)

   pip install remote_ikernel

.. code:: shell

   # Set up the kernels you'd like to use

   remote_ikernel manage

.. code:: shell

   # Add a new kernel running through GrideEngine

   remote_ikernel manage --add \
      --kernel_cmd="ipython kernel -f {connection_file}" \
      --name="Python 2.7" --cpus=2 --pe=smp --interface=sge

.. code:: shell

   # Add an SSH connection to a remote machine running IJulia

   remote_ikernel manage --add \
      --kernel_cmd="/home/me/julia-903644385b/bin/julia -i --startup-file=yes --color=yes /home/me/.julia/v0.6/IJulia/src/kernel.jl {connection_file}" \
      --name="IJulia 0.6.0" --interface=ssh \
      --host=me@remote.machine --workdir='/home/me/Workdir' --language=julia

.. code:: shell

   # Set up kernels for your local virtual environments that can be run
   # from a single notebook server.

   remote_ikernel manage --add \
      --kernel_cmd="/home/me/Virtualenvs/dev/bin/ipython kernel -f {connection_file}" \
      --name="Python 2 (venv:dev)" --interface=local

.. code:: shell

   # Connect to a SLURM cluster through a gateway machine (to get into a
   # local network) and cluster frontend machine (where the sqsub runs from).

   remote_ikernel manage --add \
      --kernel_cmd="ipython kernel -f {connection_file}" \
      --name="Python 2.7" --cpus=4 --interface=slurm \
      --tunnel-hosts gateway.machine cluster.frontend


The kernel spec files will be installed so that the new kernel appears in
the drop-down list in the notebook. ``remote_ikernel manage`` also has options
to show and delete existing kernels.


Connection multiplexing
=======================

When working with remote machines, each kernel creates two ``ssh``
connections. If you would like to reduce that, you can set up automatic
multiplexing of connections. For each machine, add a configuration to your
``~/.ssh/config``:

.. code::

   Host myhost.ac.uk
       ControlMaster auto
       ControlPath ~/.ssh/%r@%h:%p
       ControlPersist 1

This will create a master connection that remains in the background when and
multiplex everything through that. If you have multiple hops, this will need
to be added for each hop. Note, for the security conscious, that idle kernels
on multiplexed connections allow new ssh connections to be started without a
password.


Changes for v0.4
================

  * Option ``--tunnel-hosts``. When given, the software will try to create
    an ssh tunnel through all the hosts before starting the final connection.
    Allows using batch queues on remote systems.
  * Preliminary support for dealing with passwords. If a program is defined
    in the environment variable ``SSH_ASKPASS`` it will be used
    to ask the user for a password.
  * ``--launch-cmd`` can be used to override the command used to launch the
    interactive jobs on the cluster, e.g. to replace ``qlogin`` with ``qrsh``.
  * Platform LSF support.
  * The kernel json files are given unique names.

Changes for v0.3
================

  * Updated pip requirements to pull in the `notebook` package. Use an earlier
    version if you need to use IPython 3.
  * Remote process is polled for output which will show up when ``--verbose``
    if used as a kernel option.

Changes for v0.2
================

  * Version 0.2.11 is the last version to support IPython notebook version 3.
    `pip` requirements enforce versions less than 4. Use a more recent version
    to ensure compatibility with the Jupyter split.
  * Support for PBS/Torque through ``qsub -I``.
  * Tunnels are kept alive better, if something is not responding try waiting
    20 seconds to see if a tunnel had dies. (Tunnels no longer depend on pyzmq,
    instead they are launched through pexpect and monitored until they die.)
  * ``--remote-launch-args`` can be used to set ``qlogin`` parameters or similar.
  * ``--remote-precmd`` allows execution of an extra command on the remote host
    before launching a kernel.
  * Better compatibility with Python 3.
  * Kernel output on terminals with ``--verbose`` option for debugging.
  * Connect to a host with ssh, slurm, or local kernels.
  * Changed prefix to ``rik_``.
  * kernel_cmd now requires the ``{connection_file}`` argument.
  * ``remote_ikernel manage --show`` command to show existing kernels.
  * Specify the working directory on the remote machine with ``--workdir``.
  * ``kernel-uuid.json`` is copied to the working director for systems where
    there is no access to the frontend filesystem.
  * Added compatibility layer to get rid of Jupyter warnings.
