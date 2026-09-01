LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        # Hypercorn loggers
        "hypercorn": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "hypercorn.error": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "hypercorn.access": {
            "handlers": ["console"],
            "level": "WARNING",  # or INFO if you want full access logs
            "propagate": False,
        },

        # LLM-related libraries
        "openai": {
            "handlers": ["console"],
            "level": "DEBUG",  # or INFO in prod
            "propagate": True,
        },
        "langchain": {
            "handlers": ["console"],
            "level": "DEBUG",  # or INFO/WARNING in prod
            "propagate": True,
        },
        # Optionally also:
        "langchain_core": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
    # Root logger – for your app modules using logging.getLogger(__name__)
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
