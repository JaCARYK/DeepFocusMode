#!/usr/bin/env python3
"""
Deep Focus Mode - Main Application Entry Point
Production-grade intelligent distraction blocker for software engineers.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

import click
import uvicorn
from dotenv import load_dotenv

from src.api.server import app, process_monitor, keystroke_monitor
from src.db.database import db_manager
from src.db.models import Rule, BlockAction
from src.utils.config import Config
from src.utils.logger import setup_logging


# Load environment variables
load_dotenv()

# Set up logging
logger = setup_logging()


class DeepFocusMode:
    """Main application controller for Deep Focus Mode."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize Deep Focus Mode application.
        
        Args:
            config_path: Optional path to configuration file.
        """
        self.config = Config(config_path)
        self.server_task = None
        self.monitor_task = None
        self.is_running = False
        
    async def initialize_database(self):
        """Initialize database and create default rules if needed."""
        logger.info("Initializing database...")
        await db_manager.init_db()
        
        # Check if we need to create default rules
        from sqlalchemy import select
        async with db_manager.get_session() as session:
            result = await session.execute(select(Rule).limit(1))
            has_rules = result.scalar_one_or_none() is not None
            
            if not has_rules:
                logger.info("Creating default blocking rules...")
                await self._create_default_rules(session)
                await session.commit()
    
    async def _create_default_rules(self, session):
        """Create default blocking rules for common distracting sites."""
        default_rules = [
            {
                "name": "YouTube",
                "domain_pattern": "*youtube.com*",
                "action": BlockAction.CONDITIONAL,
                "required_focus_minutes": 30,
                "reminder_message": "📺 Focus for 30 minutes to unlock YouTube",
                "priority": 90
            },
            {
                "name": "Twitter/X",
                "domain_pattern": "*twitter.com*",
                "action": BlockAction.BLOCK,
                "reminder_message": "🐦 Twitter is blocked during focus time",
                "priority": 95
            },
            {
                "name": "Reddit",
                "domain_pattern": "*reddit.com*",
                "action": BlockAction.DELAY,
                "delay_minutes": 5,
                "reminder_message": "👽 Taking a 5-minute delay before Reddit",
                "priority": 85
            },
            {
                "name": "Facebook",
                "domain_pattern": "*facebook.com*",
                "action": BlockAction.BLOCK,
                "reminder_message": "📘 Facebook is blocked during focus time",
                "priority": 90
            },
            {
                "name": "Instagram",
                "domain_pattern": "*instagram.com*",
                "action": BlockAction.BLOCK,
                "reminder_message": "📷 Instagram is blocked during focus time",
                "priority": 90
            },
            {
                "name": "TikTok",
                "domain_pattern": "*tiktok.com*",
                "action": BlockAction.BLOCK,
                "reminder_message": "🎵 TikTok is blocked during focus time",
                "priority": 95
            },
            {
                "name": "Netflix",
                "domain_pattern": "*netflix.com*",
                "action": BlockAction.CONDITIONAL,
                "required_focus_minutes": 60,
                "reminder_message": "🎬 Focus for 1 hour to unlock Netflix",
                "priority": 80
            },
            {
                "name": "Twitch",
                "domain_pattern": "*twitch.tv*",
                "action": BlockAction.DELAY,
                "delay_minutes": 10,
                "reminder_message": "🎮 Taking a 10-minute delay before Twitch",
                "priority": 75
            }
        ]
        
        for rule_data in default_rules:
            rule = Rule(**rule_data)
            session.add(rule)
        
        logger.info(f"Created {len(default_rules)} default blocking rules")
    
    async def start_monitors(self):
        """Start process and keystroke monitoring."""
        logger.info("Starting activity monitors...")
        
        # Start keystroke monitor (runs in thread)
        keystroke_monitor.start_monitoring()
        
        # Start process monitor (async task)
        self.monitor_task = asyncio.create_task(
            process_monitor.start_monitoring()
        )
        
        logger.info("Activity monitors started successfully")
    
    async def start_api_server(self):
        """Start the FastAPI server."""
        logger.info(f"Starting API server on {self.config.api_host}:{self.config.api_port}")
        
        config = uvicorn.Config(
            app=app,
            host=self.config.api_host,
            port=self.config.api_port,
            log_level="info",
            access_log=True
        )
        server = uvicorn.Server(config)
        
        self.server_task = asyncio.create_task(server.serve())
        
    async def run(self):
        """Run the main application."""
        self.is_running = True
        
        try:
            # Initialize database
            await self.initialize_database()
            
            # Start monitors
            await self.start_monitors()
            
            # Start API server
            await self.start_api_server()
            
            logger.info("="*50)
            logger.info("🚀 Deep Focus Mode is running!")
            logger.info(f"📡 API Server: http://{self.config.api_host}:{self.config.api_port}")
            logger.info("🔌 Browser extension can now connect")
            logger.info("="*50)
            
            # Keep running until interrupted
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shutdown the application."""
        logger.info("Shutting down Deep Focus Mode...")
        
        self.is_running = False
        
        # Stop monitors
        keystroke_monitor.stop_monitoring()
        process_monitor.stop_monitoring()
        
        # Cancel tasks
        if self.monitor_task:
            self.monitor_task.cancel()
        if self.server_task:
            self.server_task.cancel()
        
        # Close database
        await db_manager.close()
        
        logger.info("Shutdown complete")
    
    def handle_signal(self, sig, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {sig}")
        self.is_running = False


@click.command()
@click.option(
    '--host',
    default='localhost',
    help='API server host'
)
@click.option(
    '--port',
    default=5000,
    type=int,
    help='API server port'
)
@click.option(
    '--config',
    type=click.Path(exists=True),
    help='Path to configuration file'
)
@click.option(
    '--debug',
    is_flag=True,
    help='Enable debug mode'
)
@click.option(
    '--reset-db',
    is_flag=True,
    help='Reset database (WARNING: deletes all data)'
)
def main(host: str, port: int, config: Optional[str], debug: bool, reset_db: bool):
    """
    Deep Focus Mode - Intelligent Distraction Blocker
    
    A production-grade focus assistant that helps software engineers
    stay productive by intelligently blocking distracting websites.
    """
    # Configure logging level
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create application instance
    config_path = Path(config) if config else None
    app_instance = DeepFocusMode(config_path)
    
    # Override config with CLI options
    app_instance.config.api_host = host
    app_instance.config.api_port = port
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, app_instance.handle_signal)
    signal.signal(signal.SIGTERM, app_instance.handle_signal)
    
    async def run_app():
        """Async wrapper for running the application."""
        if reset_db:
            logger.warning("Resetting database...")
            await db_manager.drop_db()
            await db_manager.init_db()
            logger.info("Database reset complete")
        
        await app_instance.run()
    
    try:
        # Run the application
        asyncio.run(run_app())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()