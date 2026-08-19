import asyncio
import logging
import sys

from handlers import build_application
import railway_api as api

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

async def main():
    application = build_application()
    # Start the bot
    await application.initialize()
    await application.start()
    # Run polling
    await application.updater.start_polling()
    logger.info("Bot started polling...")
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        asyncio.run(api.railway_api.close())