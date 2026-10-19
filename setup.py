from setuptools import setup, find_packages

setup(
    name="neuroquant-lob",
    version="1.1.0",
    author="Arunjyoti Sarma",
    description="Digital Neuromorphic Spiking Engine for Asynchronous Microstructure Alpha & Execution",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/arunjyotisarmarsece24-jpg/neuroquant-lob",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.10",
    install_requires=[
        "numpy>=1.26.0",
        "pandas>=2.2.0",
        "scipy>=1.14.0",
        "torch>=2.2.0",
        "flask>=3.0.0",
        "rich>=13.7.0",
        "requests>=2.31.0",
        "psutil>=5.9.0",
        "qrcode>=7.4.2"
    ],
    entry_points={
        "console_scripts": [
            "neuroquant=neuroquant.cli:main",
        ],
    },
)
