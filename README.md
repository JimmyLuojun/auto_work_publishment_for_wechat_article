# Auto Work Publishment for WeChat Article

A Python tool to automatically publish articles to WeChat Official Account from Markdown files.

## Features

- Parse Markdown files into structured article content
- Convert articles to WeChat-compatible HTML format
- Upload images to WeChat servers
- Publish articles to WeChat Official Account
- Generate preview HTML for review before publishing

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/auto-work-publishment-for-wechat-article.git
cd auto-work-publishment-for-wechat-article
```

2. Install dependencies using Poetry:
```bash
poetry install
```

## Configuration

1. Create a `.env` file in the project root with your API credentials:
```env
WECHAT_APP_ID=your_app_id
WECHAT_APP_SECRET=your_app_secret
OPENAI_API_KEY=your_openai_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
```

2. Create a `config.ini` file for non-sensitive settings:
```ini
[wechat]
default_author = Your Name
timeout = 30

[paths]
input_dir = data/input
output_dir = data/output
```

## Usage

1. Prepare your article in Markdown format and place it in the `data/input` directory.

2. Run the tool:
```bash
# Generate preview HTML
poetry run python src/main.py data/input/article.md --preview

# Publish to WeChat
poetry run python src/main.py data/input/article.md
```

## Project Structure

```
auto_work_publishment_for_wechat_article/
├── .env                        # Secrets & Environment Variables
├── .gitignore                  # Git Ignore Rules
├── config.ini                  # Application Configuration
├── poetry.lock                 # Dependency Lock File
├── pyproject.toml              # Project Definition
├── README.md                   # Project Documentation
├── data/                       # Input/Output Data Storage
│   ├── input/                  # Source materials
│   └── output/                 # Generated files
├── src/                        # Source Code
│   ├── core/                   # Core Logic & Data Structures
│   ├── api/                    # External API Communication
│   ├── parsing/                # Input Data Processing
│   ├── platforms/              # Platform-Specific Implementation
│   ├── utils/                  # Utility Functions
│   └── main.py                 # Application Entry Point
└── tests/                      # Automated Tests
```

## Development

1. Install development dependencies:
```bash
poetry install --with dev
```

2. Run tests:
```bash
poetry run pytest
```

3. Format code:
```bash
poetry run black .
poetry run isort .
```

4. Type checking:
```bash
poetry run mypy .
```

## License

MIT License 