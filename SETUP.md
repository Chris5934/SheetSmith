# SheetSmith Setup Guide

This guide walks you through setting up SheetSmith from scratch.

## Prerequisites

- Python 3.10 or higher
- A Google Cloud Platform account
- An Anthropic API key OR an OpenRouter API key (OpenRouter supports multiple LLM providers)

## Step 1: Google Cloud Setup

### Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your Project ID

### Enable the Google Sheets API

1. In the Cloud Console, go to **APIs & Services > Library**
2. Search for "Google Sheets API"
3. Click **Enable**

### Create OAuth Credentials

1. Go to **APIs & Services > Credentials**
2. Click **Create Credentials > OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - User Type: External (for personal use) or Internal (for organization)
   - App name: SheetSmith
   - User support email: Your email
   - Developer contact: Your email
4. Create OAuth client ID:
   - Application type: **Desktop app**
   - Name: SheetSmith
5. Download the JSON file
6. Rename it to `credentials.json` and place it in the SheetSmith directory

## Step 2: LLM Provider Setup

Choose either Anthropic (direct) or OpenRouter (supports multiple LLM providers).

### Option A: Anthropic API Setup (Direct)

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Create an account or sign in
3. Go to **API Keys**
4. Create a new API key
5. Copy the key (you'll need it for the `.env` file)

### Option B: OpenRouter API Setup (Recommended for flexibility)

1. Go to [OpenRouter](https://openrouter.ai/)
2. Create an account or sign in
3. Go to **Keys** in your account settings
4. Create a new API key
5. Copy the key (you'll need it for the `.env` file)
6. Note: OpenRouter supports multiple models including Claude, GPT-4, and others

## Step 3: Install SheetSmith

```bash
# Clone the repository
git clone <repository-url>
cd SheetSmith

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install SheetSmith
pip install -e .
```

## Step 4: Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

### For Anthropic (Direct):
```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-api-key-here
MODEL_NAME=claude-sonnet-4-20250514
GOOGLE_CREDENTIALS_PATH=credentials.json
```

### For OpenRouter:
```
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-openrouter-key-here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
GOOGLE_CREDENTIALS_PATH=credentials.json
```

**Note**: When using OpenRouter, you only need to set `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`. You do NOT need to set `ANTHROPIC_API_KEY` or `MODEL_NAME`.

Available OpenRouter models include:
- `anthropic/claude-3.5-sonnet` (recommended)
- `anthropic/claude-3-opus`
- `openai/gpt-4`
- `openai/gpt-4-turbo`
- Many others - see [OpenRouter Models](https://openrouter.ai/models)

## Step 5: Authenticate with Google

Run the authentication command:
```bash
sheetsmith auth
```

This will:
1. Open your browser to the Google sign-in page
2. Ask you to authorize SheetSmith to access your Google Sheets
3. Save the authorization token locally

**Note**: The token is saved to `token.json` and will be reused for future sessions.

## Step 6: Run SheetSmith

### Web UI (Recommended)
```bash
sheetsmith serve
```
Then open http://localhost:8000 in your browser.

### Interactive CLI
```bash
sheetsmith interactive
```

### With a specific spreadsheet
```bash
sheetsmith interactive --spreadsheet YOUR_SPREADSHEET_ID
```

## Finding Your Spreadsheet ID

The spreadsheet ID is in the URL of your Google Sheet:
```
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit
```

For example, if your URL is:
```
https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit
```

The spreadsheet ID is: `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms`

## Troubleshooting

### "credentials.json not found"
Make sure you've downloaded the OAuth credentials from Google Cloud Console and placed the file in the SheetSmith directory.

### "Token has been expired or revoked"
Delete `token.json` and run `sheetsmith auth` again.

### "API key not valid"
Check that your `ANTHROPIC_API_KEY` in `.env` is correct and has not been revoked.

### "Permission denied" when accessing spreadsheet
Make sure:
1. You're authenticated with the Google account that has access to the spreadsheet
2. The spreadsheet is shared with your Google account (or is owned by you)

### Connection errors
- Check your internet connection
- Verify the Google Sheets API is enabled in your Google Cloud project
- Check that you haven't exceeded API quotas

## Security Notes

- **Never commit credentials**: The `.gitignore` file excludes sensitive files, but always double-check before committing
- **Token storage**: OAuth tokens are stored locally in `token.json`
- **API keys**: Keep your Anthropic API key secret; rotate it if compromised
- **Spreadsheet access**: SheetSmith only accesses spreadsheets you explicitly connect to

## Next Steps

Once set up, try these commands in the web UI or CLI:

1. **Connect a spreadsheet**: Enter your spreadsheet ID in the sidebar
2. **Search for formulas**: "Find all formulas containing SWITCH"
3. **Update a value**: "Update Corruption from 28.6% to 30.0% everywhere"
4. **Store a rule**: "Remember that we always use TRIM() when comparing strings"

See the README.md for more usage examples and API documentation.
