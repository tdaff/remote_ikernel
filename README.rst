Remote IKernel
--------------

Launch IPython/Jupyter kernels on remote systems so that they can be
used with local noteboooks.

Kernels start through interactive queues on SGE clusters and
are tunneled to from the machine running the notebook.

Commands for managing the kernels are included.

Install with ``pip install remote_ikernel``.

.. code:: shell

    # install the module (python setup.py install also works)
    pip install remote_ikernel

    # Set up the kernels you'd like to use
    remote_ikernel manage

    # add a new kernel running through GrideEngine
    remote_ikernel manage --add \
        --kernel_cmd="ipython kernel -f {connection_file}" \
        --name="Python 2.7" --cpus=2 --pe=smp --interface=sge

    # add an SSH connection to a remote machine
    remote_ikernel manage --add \
        --kernel_cmd="/remote/location/of/ipython kernel -f {connection_file}" \
        --name="Python 2.7" --interface=ssh --host=me@remote.machine
        --workdir='/home/me/Workdir'

The kernel spec files will be installed so that the new kernel appears in
the drop-down list in the notebook.

Changes for v0.2
================

  * Connect to a host with ssh.
  * Changed prefix to 'rik_'.
  * kernel_cmd now requires the {connection_file} argument.
  * ``remote_ikernel manage --show`` command to show existing kernels.
  * Specify the working directory on the remote machine with ``--workdir``.
  * ``kernel-uuid.json`` is copied to the working director for systems where
    there is no access to the frontend filesystem.
