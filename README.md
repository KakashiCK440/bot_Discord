# Discord Guild Management Bot

A comprehensive Discord bot for managing guild members, war participation, and player profiles with multi-language support (English/Arabic).

## Features

### 👥 Profile Management
- `/setupprofile` - Guided profile setup with language selection
- `/profile` - View your profile
- `/resetbuild` - Change your build type
- `/deleteprofile` - Delete a user's profile (admin only)

### ⚔️ War System
- `/warpoll` - Create war participation poll
- `/warlist` - View war participants
- `/resetwar` - Reset war data (admin only)
- Automatic war reminders
- Weekly poll scheduling

### 🎮 Build System
- Support for multiple build types (DPS, Tank, Support, Healer)
- Weapon tracking
- Build-specific configurations

### 🚪 Join Request System
- Automated join request workflow
- Power requirement validation
- Admin approval system
- Automatic role assignment upon approval
- Arabic language support by default

### 🌍 Multi-Language Support
- English and Arabic languages
- User-specific language preferences
- Localized messages and UI

## Setup

### Prerequisites
- Python 3.8+
- Discord Bot Token
- Discord Server with appropriate permissions

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd files
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file:
```env
DISCORD_TOKEN=your_bot_token_here
```

4. Configure the bot:
- Edit `bot_config.py` for bot settings
- Edit `config.py` for build and weapon configurations

5. Run the bot:
```bash
python bot.py
```

## Configuration

### Bot Settings (`bot_config.py`)
- War poll check intervals
- Reminder timings
- Web server port
- Timezone settings

### Build Configuration (`config.py`)
- Build types and descriptions
- Weapon lists
- Build-specific settings

## Database

The bot uses SQLite for data persistence. Database file: `data/bot_data.db`

Tables:
- `players` - Player profiles
- `player_weapons` - Player weapon inventory
- `war_participants` - War participation tracking
- `join_requests` - Join request management
- `user_languages` - Language preferences
- `server_settings` - Server-specific configurations

## Commands

### User Commands
- `/setupprofile` - Set up your profile
- `/profile [@user]` - View profile
- `/resetbuild` - Change your build

### Admin Commands
- `/warpoll` - Create war poll
- `/warlist` - View war participants
- `/resetwar` - Reset war data
- `/deleteprofile @user` - Delete user profile
- `/postjoin` - Post join request button
- `/setupjoin` - Configure join system

## Project Structure

```
files/
├── bot.py              # Main bot entry point
├── bot_config.py       # Bot configuration
├── config.py           # Build/weapon configuration
├── database.py         # Database operations
├── locales.py          # Language loader
├── locales.json        # Translations
├── requirements.txt    # Python dependencies
├── cogs/              # Command modules
│   ├── admin.py       # Admin commands
│   ├── build.py       # Build management
│   ├── join.py        # Join system
│   ├── profile.py     # Profile commands
│   └── war.py         # War system
├── utils/             # Utility functions
│   ├── helpers.py     # General helpers
│   └── war_helpers.py # War-specific helpers
└── views/             # Discord UI components
    ├── build_views.py    # Build selection UI
    ├── join_views.py     # Join request UI
    └── profile_views.py  # Profile setup UI
```

## Contributing

Feel free to submit issues and pull requests!

## License

This project is licensed under the MIT License.
