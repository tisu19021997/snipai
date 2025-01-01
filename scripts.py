def ruff_format() -> None:
    import subprocess

    subprocess.run(["ruff", "format", "."], check=True)


def format_check() -> None:
    import subprocess

    subprocess.run(["ruff", "format", ".", "--check"], check=True)


def lint() -> None:
    import subprocess

    subprocess.run(["ruff", "check", "."], check=True)


def lint_fix() -> None:
    import subprocess

    subprocess.run(["ruff", "check", ".", "--fix"], check=True)
