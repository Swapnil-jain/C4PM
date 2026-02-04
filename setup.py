from setuptools import setup, find_packages

setup(
    name="c4pm",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "typer>=0.9.0",
        "rich>=13.0.0",
        "openai>=1.75.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "c4pm=c4pm.cli:app",
        ],
    },
)
