Remote IKernel

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
    # add a new kernel
    remote_ikernel manage --add --kernel_cmd='ipython kernel' \
                                --name="Python 2.7" \
                                --interface=sge \
                                --cpus=4 --pe=smp

The kernel spec will be installed so that the new kernel appears in
the drop-down list in the notebook.

