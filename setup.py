#from distutils.core import setup
from setuptools import setup

setup(name='remote_ikernel',
      version='0.2',
      description='Running IPython kernels through batch queues',
      long_description=open('README.rst').read(),
      author='Tom Daff',
      author_email='tdd20@cam.ac.uk',
      license='BSD',
      url='https://bitbucket.org/tdaff/remote_ikernel',
      packages=['remote_ikernel'],
      scripts=['bin/remote_ikernel'],
      install_requires=['ipython', 'pexpect'],
      classifiers=[
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 3',
          'Framework :: IPython',
          'License :: OSI Approved :: BSD License'])
