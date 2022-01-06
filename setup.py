import os

import setuptools


def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname)) as f:
        return f.read()


setuptools.setup(
    name="odoo-connect",
    version="0.0.1",
    author="Krzysztof Magusiak",
    author_email="chrmag@poczta.onet.pl",
    description="""Simple RPC client for Odoo""",
    keywords="odoo rpc",
    url="https://github.com/kmagusiak/kmagusiak-pip",
    packages=['odoo_connect'],
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    # https://pypi.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Framework :: Odoo",
    ],
    python_requires=">=3.6",
    setup_requires=[
        'setuptools_scm',
    ],
    use_scm_version={
        "local_scheme": "no-local-version",
    },
    install_requires=[
        'requests',
    ],
)
