import pathlib

import setuptools

# The directory containing this file
HERE = pathlib.Path(__file__).parent
README = HERE / "README.md"


setuptools.setup(
    name="odoo-connect",
    version="0.1",
    author="Krzysztof Magusiak",
    author_email="chrmag@poczta.onet.pl",
    description="""Simple RPC client for Odoo""",
    keywords="odoo rpc",
    url="https://github.com/kmagusiak/kmagusiak-pip",
    packages=setuptools.find_packages(exclude=['tests']),
    long_description=README.read_text(),
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
