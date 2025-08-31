#!/usr/bin/env python3
"""
Pool Temperature Logger

A secure, robust application for logging pool and air temperatures
from Aqualink systems to a PostgreSQL database.
"""

import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2 import sql
from iaqualink.client import AqualinkClient
from iaqualink.exception import AqualinkException


class Constants:
    """Application constants."""
    SECONDS_PER_MINUTE = 60
    DEFAULT_INTERVAL_MINUTES = 60
    DEFAULT_DB_PORT = 5432
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAY_SECONDS = 5


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str
    database: str
    user: str
    password: str
    port: int = Constants.DEFAULT_DB_PORT

    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create database config from environment variables."""
        return cls(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'atticdb'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            port=int(os.getenv('DB_PORT', str(Constants.DEFAULT_DB_PORT)))
        )


@dataclass
class AqualinkConfig:
    """Aqualink configuration."""
    username: str
    password: str

    @classmethod
    def from_env(cls) -> 'AqualinkConfig':
        """Create Aqualink config from environment variables."""
        username = os.getenv('AQUALINK_USERNAME')
        password = os.getenv('AQUALINK_PASSWORD')
        
        if not username or not password:
            raise ValueError(
                "AQUALINK_USERNAME and AQUALINK_PASSWORD environment variables are required"
            )
        
        return cls(username=username, password=password)


@dataclass
class TemperatureData:
    """Temperature data container."""
    pool_temp: Optional[float]
    air_temp: Optional[float]
    system_id: str
    timestamp: Optional[datetime] = None


class DatabaseManager:
    """Handles database operations."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.config.host,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                port=self.config.port
            )
            yield conn
        except psycopg2.Error as e:
            self.logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def setup_table(self) -> None:
        """Initialize database table if it doesn't exist."""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS pool (
            id SERIAL PRIMARY KEY,
            tz TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pool_temp REAL,
            air_temp REAL
        );
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(create_table_query)
                    conn.commit()
            
            self.logger.info("Database table 'pool' ready")
        except psycopg2.Error as e:
            self.logger.error(f"Error setting up database table: {e}")
            raise

    def insert_temperature_data(self, temp_data_list: List[TemperatureData]) -> None:
        """Insert temperature data into database."""
        if not temp_data_list:
            self.logger.info("No temperature data to log")
            return

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    for data in temp_data_list:
                        cursor.execute(
                            "INSERT INTO pool (tz, pool_temp, air_temp) VALUES (CURRENT_TIMESTAMP, %s, %s)",
                            (data.pool_temp, data.air_temp)
                        )
                    conn.commit()

            # Log summary
            for data in temp_data_list:
                pool_temp_str = f"{data.pool_temp}°F" if data.pool_temp is not None else 'N/A'
                air_temp_str = f"{data.air_temp}°F" if data.air_temp is not None else 'N/A'
                self.logger.info(
                    f"Logged to DB - System: {data.system_id}, "
                    f"Pool: {pool_temp_str}, Air: {air_temp_str}"
                )

        except psycopg2.Error as e:
            self.logger.error(f"Database error while logging temperature: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error while logging: {e}")
            raise


class AqualinkManager:
    """Handles Aqualink API operations."""

    def __init__(self, config: AqualinkConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _convert_to_float(value: Any) -> Optional[float]:
        """Convert string value to float, return None if invalid."""
        try:
            return float(value) if value else None
        except (ValueError, TypeError):
            return None

    async def get_temperature_data(self) -> List[TemperatureData]:
        """Get current pool temperature from Aqualink system."""
        temp_data_list = []
        
        try:
            async with AqualinkClient(self.config.username, self.config.password) as client:
                systems = await client.get_systems()

                for system_id, system_obj in systems.items():
                    try:
                        devices = await system_obj.get_devices()
                        
                        pool_temp = None
                        air_temp = None

                        # Extract and convert temperatures
                        if 'pool_temp' in devices:
                            pool_temp_raw = devices['pool_temp'].data.get('state', '')
                            pool_temp = self._convert_to_float(pool_temp_raw)

                        if 'air_temp' in devices:
                            air_temp_raw = devices['air_temp'].data.get('state', '')
                            air_temp = self._convert_to_float(air_temp_raw)

                        # Only include if we have at least one temperature reading
                        if pool_temp is not None or air_temp is not None:
                            temp_data_list.append(TemperatureData(
                                pool_temp=pool_temp,
                                air_temp=air_temp,
                                system_id=system_id,
                                timestamp=datetime.now()
                            ))

                    except AqualinkException as e:
                        self.logger.error(f"Error getting devices for system {system_id}: {e}")
                        continue

        except AqualinkException as e:
            self.logger.error(f"Error connecting to Aqualink: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error getting temperature data: {e}")

        return temp_data_list


class PoolTempLogger:
    """Main application class for logging pool temperatures."""

    def __init__(self, aqualink_config: AqualinkConfig, db_config: DatabaseConfig):
        self.aqualink_manager = AqualinkManager(aqualink_config)
        self.db_manager = DatabaseManager(db_config)
        self.logger = logging.getLogger(__name__)
        self._shutdown_requested = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self._shutdown_requested = True

    def setup(self) -> None:
        """Initialize the application."""
        self.logger.info("Setting up Pool Temperature Logger...")
        self.db_manager.setup_table()

    async def run_once(self) -> None:
        """Run a single temperature check and log."""
        self.logger.info(f"Checking pool temperature at {datetime.now()}")
        
        try:
            temp_data_list = await self.aqualink_manager.get_temperature_data()
            self.db_manager.insert_temperature_data(temp_data_list)
            
            if temp_data_list:
                self.logger.info(f"Successfully logged {len(temp_data_list)} temperature readings")
            else:
                self.logger.warning("No temperature data retrieved")
                
        except Exception as e:
            self.logger.error(f"Error during temperature check: {e}")
            raise

    async def run_continuous(self, interval_minutes: int = Constants.DEFAULT_INTERVAL_MINUTES) -> None:
        """Run temperature logging continuously."""
        self.logger.info(
            f"Starting continuous pool temperature logging every {interval_minutes} minutes..."
        )
        self.logger.info("Press Ctrl+C to stop")

        try:
            while not self._shutdown_requested:
                await self.run_once()
                
                if not self._shutdown_requested:
                    self.logger.info(f"Waiting {interval_minutes} minutes until next check...")
                    
                    # Sleep in small chunks to allow for responsive shutdown
                    sleep_duration = interval_minutes * Constants.SECONDS_PER_MINUTE
                    for _ in range(sleep_duration):
                        if self._shutdown_requested:
                            break
                        await asyncio.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Error in continuous run: {e}")
            raise
        finally:
            self.logger.info("Temperature logger stopped")


def setup_logging(level: str = 'INFO') -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('pool_logger.log')
        ]
    )


async def main() -> None:
    """Main application entry point."""
    # Setup logging
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    setup_logging(log_level)
    logger = logging.getLogger(__name__)

    try:
        # Load configuration from environment
        aqualink_config = AqualinkConfig.from_env()
        db_config = DatabaseConfig.from_env()
        
        # Get interval from environment
        interval_minutes = int(os.getenv('INTERVAL_MINUTES', str(Constants.DEFAULT_INTERVAL_MINUTES)))
        
        # Create and setup logger
        pool_logger = PoolTempLogger(aqualink_config, db_config)
        pool_logger.setup()

        # Run mode selection
        run_mode = os.getenv('RUN_MODE', 'continuous').lower()
        
        if run_mode == 'once':
            logger.info("Running in single-check mode")
            await pool_logger.run_once()
        else:
            logger.info("Running in continuous mode")
            await pool_logger.run_continuous(interval_minutes)

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


