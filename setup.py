from setuptools import setup


def parse_requirements():
    with open('requirements.txt', 'r') as f:
        return f.read().splitlines()


setup(
    name='polyswarm-client',
    version='0.1.2',
    description='Client library to simplify interacting with a polyswarmd instance',
    author='PolySwarm Developers',
    author_email='info@polyswarm.io',
    url='https://github.com/polyswarm/polyswarm-client',
    license='MIT',
    python_requires='>=3.5,!=3.5.2,<4',
    install_requires=parse_requirements(),
    include_package_data=True,
    packages=['polyswarmclient', 'ambassador', 'arbiter', 'microengine', 'arbiter.verbatimdb', 'balancemanager'],
    package_dir={
        'polyswarmclient': 'src/polyswarmclient',
        'ambassador': 'src/ambassador',
        'arbiter': 'src/arbiter',
        'microengine': 'src/microengine',
        'arbiter.verbatimdb': 'src/arbiter/verbatimdb',
        'balancemanager': 'src/balancemanager'
    },
    entry_points={
        'console_scripts': [
            'ambassador=ambassador.__main__:main',
            'arbiter=arbiter.__main__:main',
            'microengine=microengine.__main__:main',
            'verbatimdbgen=arbiter.verbatimdb.__main__:main',
            'balancemanager=balancemanager.__main__:cli',
            'reporter=polyswarmclient.reporter:main',
        ],
    },
)
