# Contributing to App Energy Monitor

Thank you for your interest in contributing! This document provides guidelines for
contributing to the project.

## Code of Conduct

Be respectful and constructive in all interactions. We're building a community where
everyone feels welcome.

## How to Contribute

### Reporting Bugs
- Check existing issues to avoid duplicates
- Provide a clear title and description
- Include:
  - Your macOS version and hardware model
  - Python version
  - Steps to reproduce the bug
  - Expected vs actual behavior
  - Relevant logs or error messages

### Suggesting Features
- Check existing issues and discussions first
- Clearly describe the feature and use case
- Explain why it would be beneficial
- Provide examples if applicable

### Submitting Pull Requests

1. **Fork the repository** and create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and ensure code quality:
   ```bash
   # Run tests
   poetry run pytest tests/ -v

   # Check for syntax errors
   poetry run python -m py_compile src/*.py
   ```

3. **Commit with clear messages**:
   ```bash
   git commit -m "Add feature: description of what you added"
   ```

4. **Push to your fork** and open a Pull Request:
   - Include a clear title and description
   - Reference any related issues
   - Explain what your PR does and why

5. **Be responsive** to feedback
   - Be open to suggestions
   - Explain your reasoning if you disagree
   - Make requested changes

## Development Setup

```bash
# Clone the repository
git clone https://github.com/your-username/app-energy-monitor.git
cd app-energy-monitor

# Install dependencies
poetry install

# Run tests
poetry run pytest tests/ -v

# Test your changes
poetry run app-energy --help
```

## Licensing

By contributing to this project, you agree that:

- Your contributions will be licensed under the **Community License** (LICENSE.COMMUNITY)
- You understand that if commercial licensing is implemented, the project maintainers
  reserve the right to offer commercial licenses for the codebase (including your
  contributions)
- You have the right to contribute the code and that it doesn't violate any third-party
  rights

## Project Standards

- **Python Style**: Follow PEP 8
- **Type Hints**: Use type hints where possible
- **Tests**: Add tests for new features
- **Documentation**: Update README and docstrings as needed
- **Commits**: Use clear, descriptive commit messages

## Questions?

Feel free to:
- Open an issue with your question
- Check existing issues and discussions
- Email: willdaniels@example.com

Thank you for contributing! 🙏
