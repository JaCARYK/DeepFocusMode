# 🎯 Deep Focus Mode - Intelligent Distraction Blocker

**focus assistant for software engineers**

Deep Focus Mode is a cross-platform distraction blocker that goes beyond simple URL blocking. It intelligently detects when you're actively coding and responds to distractions with customizable rules including delayed access, conditional unlocking, and focus-time requirements.

## Features

### Smart Detection
- **Active Coding Detection**: Monitors IDE processes (VS Code, IntelliJ, PyCharm, etc.)
- **Keystroke Activity Tracking**: Detects active work sessions (privacy-focused - no keylogging)
- **Multi-Signal Analysis**: Combines process and activity data for accurate focus detection

### Intelligent Blocking
- **Block Mode**: Complete blocking during focus sessions
- **Delay Mode**: Time-delayed access with countdown
- **Conditional Mode**: Unlock sites after X minutes of focused coding
- **Priority-Based Rules**: Cascading rule evaluation system

### Analytics & Insights
- Daily focus statistics
- Productivity scoring
- Distraction attempt tracking
- Session history and patterns

### Developer-Friendly
- Clean, modular architecture
- Comprehensive test coverage
- RESTful API design
- Extensible rule engine
- Optional ML integration ready

## Architecture

```
deep-focus-mode/
├── desktop-client/          # Python backend application
│   ├── src/
│   │   ├── api/            # FastAPI server
│   │   ├── db/             # SQLAlchemy models & database
│   │   ├── monitor/        # Process & keystroke monitoring
│   │   ├── rules/          # Rule engine & evaluation
│   │   └── utils/          # Configuration & logging
│   ├── tests/              # Pytest test suite
│   └── main.py             # Application entry point
│
└── browser-extension/       # Chrome/Firefox extension
    ├── src/
    │   ├── background/     # Service worker
    │   ├── content/        # Content scripts
    │   ├── popup/          # Extension popup UI
    │   └── options/        # Settings page
    └── manifest.json       # Extension manifest
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Chrome or Firefox browser
- macOS, Windows, or Linux

### 1. Install Desktop Client

```bash
# Clone the repository
git clone https://github.com/yourusername/deep-focus-mode.git
cd deep-focus-mode/desktop-client

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

The desktop app will start on `http://localhost:5000`

### 2. Install Browser Extension

#### Chrome:
1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select the `deep-focus-mode/browser-extension` folder
5. The extension icon should appear in your toolbar

#### Firefox:
1. Open Firefox and navigate to `about:debugging`
2. Click "This Firefox"
3. Click "Load Temporary Add-on"
4. Select `manifest.json` from the `browser-extension` folder

### 3. Configure Rules

Default rules are created automatically for common distracting sites:
- YouTube (conditional - 30 min focus required)
- Twitter/X (blocked)
- Reddit (5 min delay)
- Facebook/Instagram/TikTok (blocked)
- Netflix (conditional - 60 min focus required)

## 📖 Usage

### Starting a Focus Session

1. **Automatic Detection**: The system automatically detects when you start coding in your IDE
2. **Manual Start**: Click the extension icon and press "Start Focus Session"

### Managing Rules

Access the rules dashboard at `http://localhost:5000/dashboard` or through the extension options.

#### Rule Types:
- **BLOCK**: Completely blocks access
- **DELAY**: Delays access for X minutes
- **CONDITIONAL**: Requires X minutes of focus time

#### Rule Patterns:
- Exact match: `reddit.com`
- Wildcard: `*.youtube.com*`
- Regex: `^(www\.)?twitter\.com$`

### CLI Options

```bash
python main.py --help

Options:
  --host TEXT         API server host (default: localhost)
  --port INTEGER      API server port (default: 5000)
  --config PATH       Path to configuration file
  --debug            Enable debug mode
  --reset-db         Reset database (WARNING: deletes all data)
```

## 🧪 Testing

```bash
cd desktop-client

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_rule_engine.py -v
```

## 🔌 API Documentation

The desktop client exposes a REST API for the browser extension:

### Endpoints

#### `GET /health`
Health check endpoint

#### `GET /api/status`
Get current focus session status

#### `POST /api/check-block`
Check if a URL should be blocked
```json
{
  "url": "https://youtube.com/watch?v=..."
}
```

#### `GET /api/rules`
Get all blocking rules

#### `POST /api/rules`
Create a new rule
```json
{
  "name": "Block Netflix",
  "domain_pattern": "*netflix.com*",
  "action": "block",
  "reminder_message": "Stay focused!",
  "priority": 90
}
```

#### `GET /api/stats/today`
Get today's focus statistics

## ⚙️ Configuration

Configuration file location: `~/.deep_focus_mode/config.json`

```json
{
  "api_host": "localhost",
  "api_port": 5000,
  "process_check_interval": 5,
  "keystroke_window_size": 60,
  "idle_threshold_minutes": 5,
  "enable_ml": false,
  "log_level": "INFO",
  "focus_goal": "Complete my coding tasks without distractions"
}
```

Environment variables:
- `DFM_API_HOST`: API server host
- `DFM_API_PORT`: API server port
- `DFM_DATABASE_URL`: Custom database URL
- `DFM_LOG_LEVEL`: Logging level
- `DFM_ENABLE_ML`: Enable ML features

## 🔐 Privacy & Security

- **No Keylogging**: Only tracks keystroke frequency, not actual keys
- **Local Storage**: All data stored locally on your machine
- **No Cloud Sync**: No external services or telemetry
- **Open Source**: Full transparency of code behavior

## 🚧 Roadmap

### Near Term
- [ ] Dashboard web UI for statistics visualization
- [ ] Export data to CSV/JSON
- [ ] Time-based scheduling (e.g., work hours only)
- [ ] Firefox extension support
- [ ] Linux window detection improvements

### Long Term
- [ ] Machine learning for site classification
- [ ] Team/organization features
- [ ] Mobile app companion
- [ ] Pomodoro timer integration
- [ ] IDE plugins for deeper integration

## 🤝 Contributing

Contributions are welcome! This project follows Google's engineering standards:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`pytest`)
5. Commit with clear messages (`git commit -m 'Add amazing feature'`)
6. Push to your branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Code Style
- Python: Follow PEP 8, use Black formatter
- JavaScript: ESLint with Airbnb config
- Comments: Clear, concise, and necessary
- Tests: Maintain >80% coverage

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [psutil](https://github.com/giampaolo/psutil) - Process monitoring
- [pynput](https://github.com/moses-palmer/pynput) - Input monitoring

## 💬 Support

- Issues: [GitHub Issues](https://github.com/yourusername/deep-focus-mode/issues)
- Wiki: [Documentation](https://github.com/yourusername/deep-focus-mode/wiki)
- Email: your.email@example.com

---