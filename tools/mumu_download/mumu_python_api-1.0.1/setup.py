import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="mumu-python-api",
    version="1.0.1",
    author="u-wlkjyy",
    url='https://github.com/u-wlkjyy/mumu-python-api/',
    author_email="wlkjyy@vip.qq.com",
    description="A Python API for Mumu Robot.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.9",
)