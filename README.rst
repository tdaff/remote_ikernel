Remote IKernel
--------------

Launch IPython/Jupyter kernels on remote systems so that they can be
used with local noteboooks.

Kernels start through interactive jobs in batch queue systems (only SGE
and SLURM at the moment) or through SSH connections. Once the kernel is
started, SSH tunnels are created for the communication ports are so the
notebook can talk to the kernel as if it was local.

Commands for managing the kernels are included.

Install with ``pip install remote_ikernel``. Requires ``IPython`` version
3.0 or greater and ``pexpect``. Passwordless ``ssh`` to the remote machines
is also required.

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
        --kernel_cmd="/home/me/julia-79599ada44/bin/julia -i -F /home/me/.julia/v0.3/IJulia/src/kernel.jl {connection_file}" \
        --name="IJulia 0.3.8" --interface=ssh \
        --host=me@remote.machine --workdir='/home/me/Workdir' --language=julia

.. code:: shell

    # Set up kernels for all your local virtual environments that can be run
    # from a single notebook server.

    remote_ikernel manage --add \
        --kernel_cmd="/home/me/Virtualenvs/dev/bin/ipython kernel -f {connection_file}" \
        --name="Python 2 (venv:dev)" --interface=local


The kernel spec files will be installed so that the new kernel appears in
the drop-down list in the notebook.

.. warning::
   ``IJulia`` kernels don't seem to close properly, so you may have julia
   processes lingering on your systems. To work around this edit the file
   ``~/.julia/v0.3/IJulia/src/handlers.jl`` so that ``shutdown_request``
   calls ``run(`kill $(getpid())`)`` instaed of ``exit()``.


Changes for v0.2
================

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
