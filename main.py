import sys


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "web"

    if mode == "desktop":
        from ui.app import launch
        launch()
    else:
        import uvicorn
        uvicorn.run(
            "api.main:app",
            host="0.0.0.0",
            port=8000,
            reload="--reload" in sys.argv,
        )


if __name__ == "__main__":
    main()
