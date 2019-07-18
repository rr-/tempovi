from setuptools import find_packages, setup

setup(
    name="tempovi",
    version="0.1.0",
    description="editing tempo timesheets with vim",
    author="Marcin Kurczewski",
    author_email="rr-@sakuya.pl",
    url="https://github.com/rr-/tempovi",
    packages=find_packages(),
    install_requires=["requests", "configargparse", "dateutil", "pytimeparse"],
    entry_points={"console_scripts": ["tempovi = tempovi.__main__:main"]},
)
