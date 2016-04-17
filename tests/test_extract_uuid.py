"""
test_extract_uuid.py

Check that the uuid can be extracted from filenames when
available.

"""

from uuid import UUID

from remote_ikernel.kernel import extract_uuid, RemoteIKernel


def test_extract_uuid():
    """Check that it gets the right one."""
    this_uuid = UUID("fbbdec0f-1403-48c9-b2ae-b5b5e1572068")

    full_path = ("/home/user/.local/share/jupyter/runtime/"
                 "kernel-fbbdec0f-1403-48c9-b2ae-b5b5e1572068.json")
    relative_path = ("../../.local/share/jupyter/runtime/"
                     "kernel-fbbdec0f-1403-48c9-b2ae-b5b5e1572068.json")
    no_path = "kernel-fbbdec0f-1403-48c9-b2ae-b5b5e1572068.json"

    assert extract_uuid(full_path) == this_uuid
    assert extract_uuid(relative_path) == this_uuid
    assert extract_uuid(no_path) == this_uuid


def test_no_uuid():
    """Check that it gets nothing from these."""
    full_path = ("/home/user/.local/share/jupyter/runtime/"
                 "kernel-not-a-uuid.json")
    relative_path = ("../../.local/share/jupyter/runtime/"
                     "kernel-not-a-uuid.json")
    no_path = "kernel-not-a-uuid.json"

    assert extract_uuid(full_path) is None
    assert extract_uuid(relative_path) is None
    assert extract_uuid(no_path) is None


def test_kernel_uuid():
    """Check that any kernel gets a uuid."""
    this_uuid = UUID("fbbdec0f-1403-48c9-b2ae-b5b5e1572068")
    no_path = "kernel-fbbdec0f-1403-48c9-b2ae-b5b5e1572068.json"

    test_kernel = RemoteIKernel(connection_info=no_path,
                                interface='test')
    assert test_kernel.uuid == this_uuid

    test_kernel = RemoteIKernel(connection_info='not-a-uuid.json',
                                interface='test')
    assert test_kernel.uuid is not None
    assert isinstance(test_kernel.uuid, UUID)
