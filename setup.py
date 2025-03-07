import os
from codecs import open

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

package_name = "mloader"

about = {}
with open(
    os.path.join(here, package_name, "__version__.py"), "r", "utf-8"
) as f:
    exec(f.read(), about)

with open("README.md", "r", "utf-8") as f:
    readme = f.read()


setup(
    name=about["__title__"],
    version=about["__version__"],
    description=about["__description__"],
    long_description=readme,
    long_description_content_type="text/markdown",
    url=about["__url__"],
    packages=find_packages(),
    python_requires=">=3.12",
    install_requires=[
        "Click>=8.1.8",
        "protobuf>=6.30.0",
        "requests>=2.32.3",
        "Pillow>=11.1.0",
        "python-dotenv>=1.0.1",
    ],
    license=about["__license__"],
    zip_safe=False,
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
    project_urls={"Source": about["__url__"]},
    entry_points={
        "console_scripts": [f"{about['__title__']} = mloader.__main__:main"]
    },
)
