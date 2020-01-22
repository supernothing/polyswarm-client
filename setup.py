from setuptools import find_packages, setup


# The README.md will be used as the content for the PyPi package details page on the Python Package Index.
with open("README.md", "r") as readme:
    long_description = readme.read()


setup(
    name='polyswarm-client',
    version='2.7.1',
    description='Client library to simplify interacting with a polyswarmd instance',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='PolySwarm Developers',
    author_email='info@polyswarm.io',
    url='https://github.com/polyswarm/polyswarm-client',
    license='MIT',
    python_requires='>=3.6.5,<4',
    install_requires=[
        'aiodns==1.2.0',
        'aiohttp==3.5.4',
        'aioredis==1.2.0',
        'aioresponses==0.6.0',
        'aiorwlock==0.6.0',
        'base58==0.2.5',
        'click==6.7',
        'polyswarm-artifact>=1.3.1',
        'python-json-logger==0.1.9',
        'python-magic-bin;platform_system=="Windows"',
        'python-magic==0.4.15;platform_system=="Linux"',
        'web3==4.8.2',
        'websockets==6.0',
        'yara-python==3.7.0',
    ],
    include_package_data=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'ambassador=ambassador.__main__:main',
            'arbiter=arbiter.__main__:main',
            'liveliness=liveliness.__main__:main',
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
    ]
)
