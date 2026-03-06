import sys


def main():
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        from cli.main import app

        app()
    else:
        from ui.app import launch

        launch()


if __name__ == "__main__":
    main()
