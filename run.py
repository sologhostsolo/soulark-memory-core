from memory_core.app import create_app
from memory_core.config import Settings


settings = Settings.from_env()
app = create_app(settings=settings)


if __name__ == "__main__":
    app.run(host=settings.host, port=settings.port, debug=settings.debug)