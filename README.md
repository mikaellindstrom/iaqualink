# Pool Temperature Logger for iAqualink

A robust, secure Python application for logging pool and air temperatures from iAqualink systems to a PostgreSQL database. Designed for continuous monitoring with systemd integration on Linux systems.
Tested on proxmox debian 12 LXC.

## Features

- 🌡️ **Temperature Monitoring**: Automatically logs pool and air temperatures
- 🔐 **Secure Configuration**: Environment-based credential management
- 🗄️ **PostgreSQL Integration**: Efficient database storage with proper schema
- 🔄 **Continuous Operation**: Systemd service for reliable background operation
- 📊 **Comprehensive Logging**: Structured logging with file and journal output
- 🛡️ **Error Handling**: Robust error recovery and graceful shutdown
- ⚙️ **Configurable**: Flexible intervals and operational modes

## Requirements

### System Requirements
- Python 3.7+
- PostgreSQL database
- Linux system with systemd (for service mode)
- Network access to iAqualink API

### Python Dependencies
```bash
pip install psycopg2-binary iaqualink
```

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/mikaellindstrom/iaqualink.git
cd iaqualink
```

### 2. Set up Python Environment
```bash
# Create virtual environment
python3 -m venv iaqualink_env
source iaqualink_env/bin/activate

# Install dependencies
pip install psycopg2-binary iaqualink
```

### 3. Database Setup
Ensure your PostgreSQL database is running and accessible. The application will automatically create the required `pool` table:

```sql
CREATE TABLE IF NOT EXISTS pool (
    id SERIAL PRIMARY KEY,
    tz TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pool_temp REAL,
    air_temp REAL
);
```

### 4. Configuration
Create the environment configuration file:

```bash
# Create configuration directory
sudo mkdir -p /etc/pool-logger

# Create environment file
sudo nano /etc/pool-logger/pool-logger.env
```

Add your configuration:
```bash
# iAqualink API Credentials
AQUALINK_USERNAME=your_email@example.com
AQUALINK_PASSWORD=your_secure_password

# Database Configuration
DB_HOST=your_db_host
DB_NAME=your_database_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_PORT=5432

# Application Settings
INTERVAL_MINUTES=60
LOG_LEVEL=INFO
RUN_MODE=continuous
```

### 5. Secure Configuration File
```bash
sudo chmod 600 /etc/pool-logger/pool-logger.env
sudo chown root:root /etc/pool-logger/pool-logger.env
```

## Usage

### Manual Execution

#### Single Temperature Check
```bash
source iaqualink_env/bin/activate
RUN_MODE=once python3 pool_temp_logger.py
```

#### Continuous Monitoring
```bash
source iaqualink_env/bin/activate
python3 pool_temp_logger.py
```

### Systemd Service (Recommended)

#### 1. Install Service
```bash
# Copy service file
sudo cp pooltemp.service /etc/systemd/system/

# Reload systemd configuration
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable pooltemp.service

# Start the service
sudo systemctl start pooltemp.service
```

#### 2. Service Management
```bash
# Check service status
sudo systemctl status pooltemp.service

# View live logs
sudo journalctl -u pooltemp.service -f

# Restart service
sudo systemctl restart pooltemp.service

# Stop service
sudo systemctl stop pooltemp.service

# Disable service
sudo systemctl disable pooltemp.service
```

## Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `AQUALINK_USERNAME` | Required | Your iAqualink account email |
| `AQUALINK_PASSWORD` | Required | Your iAqualink account password |
| `DB_HOST` | `localhost` | PostgreSQL server hostname |
| `DB_NAME` | `atticdb` | Database name |
| `DB_USER` | `postgres` | Database username |
| `DB_PASSWORD` | Required | Database password |
| `DB_PORT` | `5432` | Database port |
| `INTERVAL_MINUTES` | `60` | Minutes between temperature checks |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `RUN_MODE` | `continuous` | Run mode: `continuous` or `once` |

## Architecture

### Components

- **`PoolTempLogger`**: Main application orchestrator
- **`AqualinkManager`**: Handles iAqualink API interactions
- **`DatabaseManager`**: Manages PostgreSQL operations
- **`TemperatureData`**: Data container for temperature readings
- **Configuration Classes**: Type-safe configuration management

### Data Flow

1. **Authentication**: Connects to iAqualink API using credentials
2. **Data Retrieval**: Fetches temperature data from all available systems
3. **Data Processing**: Validates and converts temperature readings
4. **Database Storage**: Stores data in PostgreSQL with timestamps
5. **Logging**: Records all operations and errors
6. **Sleep/Repeat**: Waits for next interval (continuous mode)

## Database Schema

The application creates and uses the following table structure:

```sql
CREATE TABLE pool (
    id SERIAL PRIMARY KEY,
    tz TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pool_temp REAL,
    air_temp REAL
);
```

## Logging

### Log Locations
- **Console Output**: Real-time logging to stdout
- **Log File**: `pool_logger.log` in working directory
- **System Journal**: `journalctl -u pooltemp.service`

### Log Levels
- **DEBUG**: Detailed debugging information
- **INFO**: General operational information
- **WARNING**: Warning messages for non-critical issues
- **ERROR**: Error messages for failures

## Troubleshooting

### Common Issues

#### 1. Authentication Errors
```bash
# Check credentials in environment file
sudo cat /etc/pool-logger/pool-logger.env

# Test credentials manually
RUN_MODE=once LOG_LEVEL=DEBUG python3 pool_temp_logger.py
```

#### 2. Database Connection Issues
```bash
# Test database connectivity
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT NOW();"

# Check database configuration
sudo journalctl -u pooltemp.service | grep -i database
```

#### 3. Service Won't Start
```bash
# Check service status and logs
sudo systemctl status pooltemp.service
sudo journalctl -u pooltemp.service --since "10 minutes ago"

# Verify file permissions
ls -la /etc/pool-logger/pool-logger.env
```

#### 4. Network Connectivity
```bash
# Test network connectivity to iAqualink
ping support.iaqualink.com

# Check firewall settings
sudo ufw status
```

### Debug Mode

Enable debug logging for detailed troubleshooting:
```bash
# Edit environment file
sudo nano /etc/pool-logger/pool-logger.env

# Change LOG_LEVEL
LOG_LEVEL=DEBUG

# Restart service
sudo systemctl restart pooltemp.service

# View debug logs
sudo journalctl -u pooltemp.service -f
```

## Security Considerations

- ✅ **Credentials**: Stored in environment file with restricted permissions (600)
- ✅ **Service Hardening**: NoNewPrivileges, PrivateTmp, ProtectSystem
- ✅ **Resource Limits**: Memory and CPU quotas configured
- ✅ **Input Validation**: All inputs validated and sanitized
- ✅ **Error Handling**: No sensitive information leaked in error messages

## Development

### Running Tests
```bash
# Install development dependencies
pip install pytest pytest-asyncio pytest-mock

# Run tests (when available)
pytest tests/
```

### Code Quality
The codebase follows Python best practices:
- Type hints throughout
- Comprehensive error handling
- Structured logging
- Separation of concerns
- Environment-based configuration

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review the logs for error messages
3. Create an issue on GitHub with detailed information

## Changelog

### v2.0.0 (Latest)
- Complete rewrite with improved architecture
- Environment-based configuration
- Enhanced security and error handling
- Systemd integration
- Comprehensive logging
- Type hints and documentation

### v1.0.0
- Initial version with basic functionality
