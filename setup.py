import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="squeezebox-controller",
    version="0.11",
    author="Jackoson",
    description="A python api for controlling logitech squeezeboxes via the squeezebox server.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jackoson/squeezebox-controller",
    packages=setuptools.find_packages(),
    install_requires=[
      'requests', 'pylev'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)