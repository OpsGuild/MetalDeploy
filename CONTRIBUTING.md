# Contributing to MetalDeploy Action

Thank you for your interest in contributing to MetalDeploy Action! This document provides guidelines and instructions for contributing.

## How to Contribute

### Reporting Issues

If you find a bug or have a feature request, please open an issue on GitHub with:
- A clear description of the problem or feature
- Steps to reproduce (for bugs)
- Expected vs actual behavior
- Your environment details (OS, GitHub Actions version, etc.)

### Submitting Pull Requests

1. **Fork the repository** and create a new branch from `main`
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Set up pre-commit hooks** (recommended):
   ```bash
   pip install pre-commit
   pre-commit install
   ```
   This will automatically format and lint your code before commits.

3. **Make your changes** following the code style and conventions

4. **Test your changes** if possible (manual testing is acceptable)

5. **Update documentation** if you've changed functionality

6. **Commit your changes** with clear, descriptive messages
   ```bash
   git commit -m "Add feature: description of what you added"
   ```

7. **Push to your fork** and open a Pull Request
   ```bash
   git push origin feature/your-feature-name
   ```

8. **Describe your changes** in the PR description:
   - What changed and why
   - How to test the changes
   - Any breaking changes

## Code Style

- Follow Python PEP 8 style guidelines
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions focused and single-purpose

## Documentation

- Update README.md if you add new features or change existing ones
- Keep code comments clear and helpful
- Update example workflows if behavior changes

## Testing

This project includes a comprehensive test suite. Before submitting a PR, please ensure all tests pass.

See [tests/README.md](tests/README.md) for detailed testing documentation, including:
- How to run tests
- How to write new tests
- Test structure and best practices
- Coverage reporting

## Questions?

Feel free to open an issue for questions or discussions about contributions.

Thank you for contributing! 🎉
