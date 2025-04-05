# WeChat Markdown Auto Publisher

Automates the process of converting Markdown articles, handling associated media (cover images, content images/videos), generating summaries, and publishing them as drafts to a WeChat Official Account.

## Features

* Parses Markdown files with YAML frontmatter for metadata (title, author, cover image).
* Converts Markdown content to HTML suitable for WeChat.
* Handles media assets:
    * **Pre-prepared Mode:** Uses existing images/videos linked via frontmatter, custom  tags, or standard Markdown links relative to the input directory structure.
    * **API-generated Mode:** (Placeholder for future implementation) Intended to generate media via APIs like DALL-E.
* Uploads necessary media (cover 'thumb', content images/videos) to WeChat to get  and URL.
* Injects uploaded media URLs correctly into the final HTML content.
* Optionally generates article summaries/abstracts using the DeepSeek API.
* Publishes the complete article as a draft to your WeChat Official Account.
* Supports basic idempotency check (attempts to update existing drafts with the same title).
* Configurable via  and  file for secrets.

## Project Structure

/Users/junluo/Documents/auto_work_publishment_for_wechat_article
├── .gitignore
├── config.ini                # Non-sensitive configuration
├── pyproject.toml            # Project metadata and dependencies
├── README.md                 # This file
├── secrets/                  # Optional: Directory for .env file
│   └── .env.example          # Example environment variables
├── data/
│   ├── input/
│   │   ├── your_article.md   # Input Markdown file(s)
│   │   └── inserting_media/
│   │       ├── cover_image/  # Place cover images here (if pre-prepared)
│   │       └── content_image/# Place content images/videos here (if pre-prepared)
│   └── output/               # Generated files (ignored by git)
│       └── generated_images/ # Location for API-generated images (if used)
├── src/                      # Source code
│   ├── api/                  # API client modules (WeChat, DeepSeek, base)
│   ├── core/                 # Core logic (settings, article model)
│   ├── parsing/              # Markdown parsing logic
│   ├── platforms/            # Platform-specific logic (WeChat media/publishing)
│   ├── templates/            # HTML/CSS templates (optional)
│   ├── utils/                # Utility modules (logger)
│   ├── init.py
│   └── main.py               # Main script entry point
└── tests/                    # Unit/integration tests (optional)
## Setup & Installation

1.  **Prerequisites:**
    * Python >= 3.8
    * 
Usage:   
  pip <command> [options]

Commands:
  install                     Install packages.
  download                    Download packages.
  uninstall                   Uninstall packages.
  freeze                      Output installed packages in requirements format.
  inspect                     Inspect the python environment.
  list                        List installed packages.
  show                        Show information about installed packages.
  check                       Verify installed packages have compatible dependencies.
  config                      Manage local and global configuration.
  search                      Search PyPI for packages.
  cache                       Inspect and manage pip's wheel cache.
  index                       Inspect information available from package indexes.
  wheel                       Build wheels from your requirements.
  hash                        Compute hashes of package archives.
  completion                  A helper command used for command completion.
  debug                       Show information useful for debugging.
  help                        Show help for commands.

General Options:
  -h, --help                  Show help.
  --debug                     Let unhandled exceptions propagate outside the
                              main subroutine, instead of logging them to
                              stderr.
  --isolated                  Run pip in an isolated mode, ignoring
                              environment variables and user configuration.
  --require-virtualenv        Allow pip to only run in a virtual environment;
                              exit with an error otherwise.
  --python <python>           Run pip with the specified Python interpreter.
  -v, --verbose               Give more output. Option is additive, and can be
                              used up to 3 times.
  -V, --version               Show version and exit.
  -q, --quiet                 Give less output. Option is additive, and can be
                              used up to 3 times (corresponding to WARNING,
                              ERROR, and CRITICAL logging levels).
  --log <path>                Path to a verbose appending log.
  --no-input                  Disable prompting for input.
  --keyring-provider <keyring_provider>
                              Enable the credential lookup via the keyring
                              library if user input is allowed. Specify which
                              mechanism to use [auto, disabled, import,
                              subprocess]. (default: auto)
  --proxy <proxy>             Specify a proxy in the form
                              scheme://[user:passwd@]proxy.server:port.
  --retries <retries>         Maximum number of retries each connection should
                              attempt (default 5 times).
  --timeout <sec>             Set the socket timeout (default 15 seconds).
  --exists-action <action>    Default action when a path already exists:
                              (s)witch, (i)gnore, (w)ipe, (b)ackup, (a)bort.
  --trusted-host <hostname>   Mark this host or host:port pair as trusted,
                              even though it does not have valid or any HTTPS.
  --cert <path>               Path to PEM-encoded CA certificate bundle. If
                              provided, overrides the default. See 'SSL
                              Certificate Verification' in pip documentation
                              for more information.
  --client-cert <path>        Path to SSL client certificate, a single file
                              containing the private key and the certificate
                              in PEM format.
  --cache-dir <dir>           Store the cache data in <dir>.
  --no-cache-dir              Disable the cache.
  --disable-pip-version-check
                              Don't periodically check PyPI to determine
                              whether a new version of pip is available for
                              download. Implied with --no-index.
  --no-color                  Suppress colored output.
  --no-python-version-warning
                              Silence deprecation warnings for upcoming
                              unsupported Pythons.
  --use-feature <feature>     Enable new functionality, that may be backward
                              incompatible.
  --use-deprecated <feature>  Enable deprecated functionality, that will be
                              removed in the future. and  (usually included with Python)

2.  **Clone Repository:**
    ```bash
    git clone <your-repository-url> # Replace with your repo URL if applicable
    cd auto_work_publishment_for_wechat_article
    ```

3.  **Create Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use 
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -e .
    ```
    *(This installs the package in editable mode based on )*

5.  **Configure Environment Variables:**
    * Create a file named  in the project root directory (or inside the  directory if you prefer, ensure  checks there).
    * Copy the contents from  (if provided) or create it from scratch.
    * **Add your secret credentials to the  file:**
        ```dotenv
        # .env file content
        WECHAT_APP_ID="your_wechat_app_id"
        WECHAT_APP_SECRET="your_wechat_app_secret"
        DEEPSEEK_API_KEY="your_deepseek_api_key"
        # OPENAI_API_KEY="your_openai_api_key" # If using OpenAI for image generation
        ```
    * **Never commit your  file to Git!** ( should prevent this).

6.  **Review Configuration ():**
    * Check the default settings in .
    * Adjust default , media , or API endpoints if necessary.

## Configuration Details

* **:** Holds sensitive API keys and credentials. Must be created manually.
* **:** Holds non-sensitive settings.
    * , : API base URLs and models.
    * : Defines relative paths for input/output/templates/secrets directories.
    * : Default author, originality settings, etc.
    * : Sets the  ( or ).

## Usage

Run the script from the project root directory (where  is located) after activating the virtual environment:

```bash
python src/main.py /path/to/your/article.md
```

Or, if the script entry point was installed correctly:

```bash
wechat-publish /path/to/your/article.md
```

**Command-line Arguments:**

*  (Required): Path to the input Markdown file.
*  (Optional): If included, the script will *not* check if a draft with the same title already exists before creating a new one. Default is to check.
*  (Optional): Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default is INFO.

**Example:**

```bash
wechat-publish data/input/my_first_article.md --log-level DEBUG
```

## Input Format & Media Handling

* **Markdown:** Use standard Markdown syntax.
* **Frontmatter (YAML):** Include metadata at the top of your  file, enclosed in :
    ```yaml
    ---
    title: Your Article Title Required
    author: Optional Author Name # Overrides config.ini default
    # Choose ONE way to specify the cover image:
    cover_image: cover_placeholder_id.jpg # ID matching a file in data/input/inserting_media/cover_image/
    # OR
    # cover_image_path: path/relative/to/input_dir/cover.png # e.g., inserting_media/cover_image/cover.png
    custom_field: any other metadata # Accessible in article.metadata
    ---
    Your markdown content starts here...
    ```
* **Media Mode ():**
    * :
        * **Cover Image:** Referenced via  or  in frontmatter. Files should reside typically in . Fallback lookup by title/first file might occur if no frontmatter ref.
        * **Content Media:**
            * Use standard Markdown:  (Path relative to the  file or  dir). The parser extracts the relative path.
            * Use custom placeholder: . The script will look for  inside .
    * : (Not yet implemented) Expected to generate images based on placeholders or context and save them to .

## Workflow Steps

1.  Load settings and validate input.
2.  Initialize API Clients and Services.
3.  Parse Markdown file (including frontmatter).
4.  Determine and locate required media files based on mode and references.
5.  Upload necessary media (cover first) to WeChat, obtaining s/URLs.
6.  Generate article summary using DeepSeek (optional).
7.  Assemble final HTML, injecting media URLs.
8.  Check for existing draft by title (optional).
9.  Create or update the draft via WeChat API.
10. Log results and cleanup.

## Troubleshooting

* **API Errors (4xxxx, 5xxxx):** Check your  file for correct API keys/secrets. Verify API base URLs in . Check WeChat/DeepSeek platform status. Increase log level () for detailed request/response info.
* **File Not Found:** Ensure media files are placed in the correct directories () and that filenames match placeholder IDs or relative paths in Markdown/frontmatter are correct. Check permissions.
* **Token Errors (WeChat):** Usually related to incorrect App ID/Secret or network issues preventing token retrieval. The client attempts auto-refresh.
* **Parsing Errors:** Ensure valid YAML frontmatter and standard Markdown syntax.

## License

This project is licensed under the MIT License - see the  file for details (or specified in ).

