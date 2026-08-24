# Telegram Support Relay Bot

A lightweight, production-ready Telegram Support Relay Bot with **no persistent database**.

## Overview

This bot acts as a live message relay between users and your support team in a Telegram group.

**Flow:**
```
User → Bot → Support Group
         ↓
Team Member (Reply in Group) → Bot → Original User
```

## Key Features

- ✅ **No Database** — All mappings are stored temporarily in RAM only
- ✅ **No User Data Storage** — No profiles, messages, or history is saved
- ✅ **Multi-Media Support** — Text, Photos, Videos, Documents, Audio, Voice, Stickers, GIFs, Video Notes, Contacts, Locations, Polls
- ✅ **Reply Routing** — Team members reply to group messages, bot forwards back to the user
- ✅ **Authorized Team Only** — Only configured `SUPPORT_MEMBER_IDS` can reply to users
- ✅ **Admin Commands** — `/start`, `/status` for admins
- ✅ **Startup Validation** — Checks bot permissions on startup
- ✅ **Error Handling** — Graceful handling of blocks, API errors, rate limits
- ✅ **Self-Message Protection** — Prevents infinite loops

## ⚠️ Important: No Persistent Storage

> This bot does not use a persistent database. User/message routing mappings are kept temporarily in process memory and are lost when the bot restarts.

## Environment Variables

Create a `.env` file (see `.env.example`) or set these in your hosting platform:

| Variable | Description | Example |
|----------|-------------|---------|
| `BOT_TOKEN` | Bot token from @BotFather | `123456:ABC-DEF...` |
| `SUPPORT_GROUP_ID` | Telegram Group ID (with `-100` prefix for supergroups) | `-1001234567890` |
| `ADMIN_IDS` | Admin Telegram User IDs (comma-separated) | `123456789,987654321` |
| `SUPPORT_MEMBER_IDS` | Support team member IDs (comma-separated) | `111111111,222222222` |

## How to Get IDs

- **Group ID**: Add `@userinfobot` or `@getidsbot` to your group
- **User ID**: Message `@userinfobot` and it will reply with your ID

## Setup Instructions

### 1. Create Bot
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token

### 2. Create Support Group
1. Create a new Telegram group
2. Add your bot to the group
3. Make the bot an **Administrator** with these permissions:
   - Delete messages
   - Restrict members
   - Pin messages
   - Manage video chats
   - Remain anonymous (optional)
   - Add new admins (optional)

### 3. Configure Environment Variables

```bash
BOT_TOKEN=your_bot_token
SUPPORT_GROUP_ID=-1001234567890
ADMIN_IDS=your_telegram_id
SUPPORT_MEMBER_IDS=id1,id2,id3
```

### 4. Deploy

#### Option A: Render (Recommended)

1. Fork/upload this repo to GitHub
2. Create a new **Web Service** on [Render](https://render.com)
3. Connect your GitHub repo
4. Set Environment Variables in Render Dashboard
5. Deploy!

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
python bot.py
```

#### Option B: Local

```bash
# Clone repo
git clone <your-repo-url>
cd telegram_support_relay_bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (or create .env file)
export BOT_TOKEN=your_token
export SUPPORT_GROUP_ID=-1001234567890
export ADMIN_IDS=your_id
export SUPPORT_MEMBER_IDS=id1,id2

# Run
python bot.py
```

## How It Works

### User Sends Message
1. User messages the bot privately
2. Bot forwards the message to the support group with user info
3. Bot stores a temporary mapping: `Group Message ID → User Chat ID`

### Team Member Replies
1. Support team member replies to the group message (using Telegram's Reply feature)
2. Bot checks if the replier is in `SUPPORT_MEMBER_IDS`
3. Bot looks up the original user from the temporary mapping
4. Bot forwards the reply back to the original user

### Restart Behavior
- When the bot restarts, all in-memory mappings are lost
- Old group message replies will not reach users (expected behavior)
- New messages will create new mappings automatically

## Supported Message Types

| Type | User → Group | Group → User |
|------|-------------|-------------|
| Text | ✅ | ✅ |
| Photo | ✅ | ✅ |
| Video | ✅ | ✅ |
| Document | ✅ | ✅ |
| Audio | ✅ | ✅ |
| Voice | ✅ | ✅ |
| Sticker | ✅ | ✅ |
| Animation/GIF | ✅ | ✅ |
| Video Note | ✅ | ✅ |
| Contact | ✅ | ✅ |
| Location | ✅ | ✅ |
| Poll | ✅ (info only) | ❌ |

## Admin Commands

| Command | Description | Access |
|---------|-------------|--------|
| `/start` | Welcome message | All users |
| `/status` | Bot status info | Admin IDs only |

## Architecture

```
┌─────────┐     ┌─────┐     ┌───────────────┐
│  User   │────→│ Bot │────→│ Support Group │
└─────────┘     └─────┘     └───────────────┘
                                    │
                                    ↓ Reply
                              ┌─────────────┐
                              │ Team Member │
                              └─────────────┘
                                    │
                                    ↓
                              ┌─────┐
                              │ Bot │
                              └─────┘
                                    │
                                    ↓
                              ┌─────────┐
                              │  User   │
                              └─────────┘
```

## Project Structure

```
telegram_support_relay_bot/
├── bot.py              # Main bot application
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## Security Notes

- Never commit `.env` to GitHub (it's in `.gitignore`)
- Never share your `BOT_TOKEN`
- Bot does not store any user data permanently
- Phone numbers and private info are never exposed in the group

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot not responding | Check `BOT_TOKEN` is correct |
| Messages not reaching group | Verify `SUPPORT_GROUP_ID` and bot is admin in group |
| Replies not reaching user | Verify replier's ID is in `SUPPORT_MEMBER_IDS` |
| Bot crashes on startup | Check logs for missing environment variables |

## License

MIT License — Free to use and modify.
