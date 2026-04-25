# Contributing to eVera

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes
4. Run tests locally
5. Submit a pull request

## Development Setup

```bash
git clone https://github.com/embeddedos-org/eVera.git
cd eVera
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## Code Guidelines

- Follow PEP 8 style
- Use type hints where practical
- Write tests for new features
- Keep commits focused and atomic

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
feat: add new feature
fix: resolve bug
docs: update documentation
test: add test coverage
```

## Pull Request Checklist

- [ ] Tests pass locally
- [ ] New features include tests
- [ ] Code follows project style
- [ ] Commit messages follow conventional commits

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
