"""Command-line interface for SheetSmith."""

import argparse
import asyncio
import sys

import uvicorn


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="SheetSmith - Agentic Google Sheets Automation Assistant"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server_parser = subparsers.add_parser("serve", help="Start the web server")
    server_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    server_parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind to (default: 8000)"
    )
    server_parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )

    # Interactive command
    interactive_parser = subparsers.add_parser(
        "interactive", help="Start an interactive CLI session"
    )
    interactive_parser.add_argument(
        "--spreadsheet", "-s", help="Default spreadsheet ID to work with"
    )

    # Auth command
    auth_parser = subparsers.add_parser(
        "auth", help="Authenticate with Google Sheets API"
    )

    args = parser.parse_args()

    if args.command == "serve":
        run_server(args.host, args.port, args.reload)
    elif args.command == "interactive":
        asyncio.run(run_interactive(args.spreadsheet))
    elif args.command == "auth":
        run_auth()
    else:
        parser.print_help()
        sys.exit(1)


def run_server(host: str, port: int, reload: bool):
    """Run the web server."""
    uvicorn.run(
        "sheetsmith.api:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


async def run_interactive(spreadsheet_id: str = None):
    """Run an interactive CLI session."""
    from .agent import SheetSmithAgent

    print("SheetSmith Interactive Mode")
    print("=" * 40)
    print("Type 'quit' or 'exit' to exit.")
    print("Type 'reset' to clear conversation.")
    if spreadsheet_id:
        print(f"Working with spreadsheet: {spreadsheet_id}")
    print()

    agent = SheetSmithAgent()
    await agent.initialize()

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit"):
                print("Goodbye!")
                break

            if user_input.lower() == "reset":
                agent.reset_conversation()
                print("Conversation reset.")
                continue

            # Add spreadsheet context if set
            message = user_input
            if spreadsheet_id and "spreadsheet" not in message.lower():
                message = f"[Spreadsheet: {spreadsheet_id}]\n{message}"

            try:
                response = await agent.process_message(message)
                print(f"\nSheetSmith: {response}\n")
            except Exception as e:
                print(f"\nError: {e}\n")

    finally:
        await agent.shutdown()


def run_auth():
    """Run the Google authentication flow."""
    from .sheets import GoogleSheetsClient

    print("Authenticating with Google Sheets API...")
    try:
        client = GoogleSheetsClient()
        # Accessing the service property triggers auth
        _ = client.service
        print("Authentication successful!")
        print("Token saved. You can now use SheetSmith with Google Sheets.")
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
