# -*- coding: utf-8 -*-

"""
test_cli.py

Check that the output of remote_ikernel is as expected when run as a
commandline script.

"""

# pytest tries to include this if Test is kept in the name
from scripttest import TestFileEnvironment as Env

# Generic just for testing
env = Env()


def test_launcher_doing_nothing():
    """Run without arguments."""
    # This says error because there are no arguments -- that's fine.
    result = env.run('remote_ikernel', expect_error=True)
    assert result.returncode != 0
    # Help is useless, really
    result = env.run('remote_ikernel', '--help')
    assert 'remote_ikernel manage' in result.stdout


def test_launcher_version():
    """Launcher not manager."""
    # version goes to stderr in PY2, stdout in PY3
    result = env.run('remote_ikernel', '-V', expect_stderr=True)
    assert 'Remote Jupyter kernel launcher' in result.stdout + result.stderr


def test_manage_doing_nothing():
    """Manage is different to the kernel itself."""
    # Does not error. Gives help.
    result = env.run('remote_ikernel', 'manage')
    assert 'usage' in result.stdout
    result = env.run('remote_ikernel', 'manage', '--help')
    assert 'usage' in result.stdout


def test_manage_basics():
    result = env.run('remote_ikernel', 'manage', '-V', expect_stderr=True)
    assert 'Remote Jupyter kernel manager' in result.stdout + result.stderr
    # Show will not error, even with no kernels
    result = env.run('remote_ikernel', 'manage', '--show')


def test_minimum_args():
    # interface, kernel_cmd and name are required!
    result = env.run('remote_ikernel', 'manage', '--add',
                     '--kernel_cmd=command', '--name=name', expect_error=True)
    assert 'interface must be specified' in result.stderr
    result = env.run('remote_ikernel', 'manage', '--add', '--interface=local',
                     '--name=name', expect_error=True)
    assert 'kernel_cmd is required' in result.stderr
    result = env.run('remote_ikernel', 'manage', '--add', '--interface=local',
                     '--kernel_cmd=command', expect_error=True)
    assert 'name is required for kernel' in result.stderr
    result = env.run('remote_ikernel', 'manage', '--add', '--interface=local',
                     '--kernel_cmd=command', '--name=name', expect_error=False)
    assert 'Added kernel' in result.stdout
    result = env.run('remote_ikernel', 'manage', '--delete', 'rik_local_name')
    assert 'Removed kernel' in result.stdout


def test_unicode():
    created = []
    # Create a unicode containing kernel with unicode in every field possible
    result = env.run('remote_ikernel', 'manage', '--add', '--interface=local',
                     '--kernel_cmd=command ☂', '--name=name ☂',
                     '--language=lang ☂', '--pe=pe ☂', '--host=host ☂',
                     '--workdir=dir ☂', '--remote-precmd=pre ☂',
                     '--launch-cmd=launch ☂', '--remote-launch-args=rla ☂',
                     '--tunnel-hosts=th ☂')
    assert u'\u2602' in result.stdout
    result = env.run('remote_ikernel', 'manage', '--show')
    assert u'\u2602' in result.stdout
    result = env.run('remote_ikernel', 'manage', '--delete',
                     'rik_local_name_launch_pe___via_th__')
    assert 'Removed kernel' in result.stdout
