#!/usr/bin/env python

from setuptools import setup

setup(name='sedfitter',
      version='1.3',
      description='SED Fitter in Python',
      author='Thomas Robitaille',
      author_email='thomas.robitaille@gmail.com',
      packages=['sedfitter',
                'sedfitter.convolve',
                'sedfitter.convolved_fluxes',
                'sedfitter.convolved_fluxes.tests',
                'sedfitter.extinction',
                'sedfitter.extinction.tests',
                'sedfitter.filter',
                'sedfitter.filter.tests',
                'sedfitter.sed',
                'sedfitter.sed.tests',
                'sedfitter.source',
                'sedfitter.source.tests',
                'sedfitter.tests',
                'sedfitter.utils',
                'sedfitter.utils.tests'],
      package_data={'sedfitter.sed.tests':['data/*.fits.gz'],
                    'sedfitter.filter.tests':['data/*.txt'],
                    'sedfitter.utils.tests':['data/*.conf', 'data/*.par']},
      provides=['sedfitter'],
      install_requires=['numpy', 'scipy', 'matplotlib', 'astropy'],
      keywords=['Scientific/Engineering'],
     )
