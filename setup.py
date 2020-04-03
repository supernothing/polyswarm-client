from setuptools import find_packages, setup


def parse_requirements():
    with open('requirements.txt', 'r') as f:
        return [
            '{2} @ {0}{1}{2}'.format(*r.partition('#egg=')) if '#egg=' in r else r
            for r in f.read().splitlines()
        ]


# The README.md will be used as the content for the PyPi package details page on the Python Package Index.
with open("README.md", "r") as readme:
    long_description = readme.read()

setup(name='polyswarm-client',
      version='2.7.4',
      description='Client library to simplify interacting with a polyswarmd instance',
      long_description=long_description,
      long_description_content_type="text/markdown",
      author='PolySwarm Developers',
      author_email='info@polyswarm.io',
      url='https://github.com/polyswarm/polyswarm-client',
      license='MIT',

      include_package_data=True,
      install_requires=parse_requirements(),
      package_dir={'': 'src'},
      packages=find_packages('src'),
      python_requires='>=3.6.5,<4',
      setup_requires=['pytest'],
      test_suite='tests',
      tests_require=['pytest-runner'],

      entry_points={
          'console_scripts': [
              'ambassador=ambassador.__main__:main',
              'arbiter=arbiter.__main__:main',
              'liveliness=liveness.__main__:main',
              'liveness=liveness.__main__:main',
              'microengine=microengine.__main__:main',
              'verbatimdbgen=arbiter.verbatimdb.__main__:main',
              'balancemanager=balancemanager.__main__:cli',
              'worker=worker.__main__:main',
          ],
      },
      classifiers=[
          "Intended Audience :: Developers",
          "License :: OSI Approved :: MIT License",
          "Operating System :: OS Independent",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: Implementation :: PyPy",
      ])
