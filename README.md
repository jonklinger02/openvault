# OpenVault

Git for engineering files. Version-control your CAD designs with meaningful metadata.

## Install

```bash
pip install openvault
```

## Quickstart

```bash
openvault init        # Initialize a repo for engineering files
openvault status      # Show modified engineering files
openvault commit      # Commit with auto-extracted STEP metadata
openvault push        # Sync with remote (LFS-aware)
```

## Development

```bash
git clone https://github.com/jonklinger02/openvault.git
cd openvault
pip install -e ".[dev]"
pytest
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
