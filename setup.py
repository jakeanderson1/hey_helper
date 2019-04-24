import setuptools


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='hey-helper',
    version='0.0.1',
    scripts=['hey_helpers.py'],
    author='John Rork',
    author_email='jnrork@gmail.com',
    description='A python wrapper for bash-like scripts',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/jakeanderson1/hey_helper',
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ]
)