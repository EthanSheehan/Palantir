import os

import structlog

logger = structlog.get_logger()

try:
    import data

    logger.info("data_package_found", file=data.__file__, path=getattr(data, "__path__", "No Path"))
    import data.historical_activity

    logger.info("historical_activity_imported")
except ImportError as exc:
    logger.error("import_failed", error=str(exc))

logger.info("cwd_contents", files=os.listdir("."))
if os.path.exists("data"):
    logger.info("data_dir_contents", files=os.listdir("data"))
