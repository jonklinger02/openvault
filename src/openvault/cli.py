import click

from openvault import __version__


@click.group()
@click.version_option(version=__version__)
def main():
    """OpenVault — Git for engineering files."""
    pass


@main.command()
def status():
    """Show repository status."""
    click.echo("OpenVault is ready.")


if __name__ == "__main__":
    main()
