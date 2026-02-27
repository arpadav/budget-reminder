# --------------------------------------------------
# external
# --------------------------------------------------
import os
import sys
import time
import threading
import webbrowser
import http.server
import socketserver
from typing import Any
from pathlib import Path
from datetime import datetime

# --------------------------------------------------
# local
# --------------------------------------------------
import primitives


def debug_mode(
    budget_summary: primitives.Summary,
    template_name: str = "budget-email.html",
    output_file: str = "output.html",
    port: int = 8000,
):
    """
    Debug mode: watch template for changes, re-render on change, and serve via HTTP.
    Press Ctrl+C or 'q' to quit.

    Args:
        budget_summary: The budget summary data to render
        template_name: Name of the template file to watch
        output_file: Output HTML file name
        port: HTTP server port
    """
    template_path = Path(template_name)
    output_path = Path(output_file)

    if not template_path.exists():
        print(f"Error: Template file '{template_name}' not found!")
        return

    # --------------------------------------------------
    # track last modification time
    # --------------------------------------------------
    last_mtime = os.path.getmtime(template_path)

    # --------------------------------------------------
    # http server setup
    # --------------------------------------------------
    class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: tuple[Any, ...]):
            pass  # suppress request logs

    def render_html():
        """Render the budget summary to HTML and write to output file"""
        try:
            html_content = budget_summary.to_email_html(template_path=template_name)
            output_path.write_text(html_content)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Rendered to {output_file}")
            return True
        except Exception as e:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] Error rendering template: {e}"
            )
            import traceback

            traceback.print_exc()
            return False

    httpd = None
    server_thread = None

    def start_server():
        """Start the HTTP server to serve the output file"""
        nonlocal httpd, server_thread
        try:
            httpd = socketserver.TCPServer(("", port), QuietHTTPRequestHandler)
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] Server started at http://localhost:{port}/{output_file}"
            )
            return True
        except OSError as e:
            if "Address already in use" in str(e):
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Port {port} already in use, server already running"
                )
                return True
            else:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Error starting server: {e}"
                )
                return False

    # --------------------------------------------------
    # initial render
    # --------------------------------------------------
    print(f"\n{'='*60}")
    print(f"DEBUG MODE - Watching '{template_name}' for changes")
    print(f"{'='*60}")
    print(f"Output file: {output_file}")
    print(f"Commands: 'r' to restart (+ optionally change port), 'q' to quit\n")
    if not render_html():
        return
    if not start_server():
        return

    # --------------------------------------------------
    # open browser
    # --------------------------------------------------
    try:
        webbrowser.open(f"http://localhost:{port}/{output_file}")
    except:
        pass

    # --------------------------------------------------
    # watch loop with quit support
    # --------------------------------------------------
    quit_flag = threading.Event()
    restart_flag = threading.Event()

    def input_thread():
        """Background thread to listen for 'q' (quit) or 'r' (restart) input"""
        nonlocal port
        try:
            while not quit_flag.is_set():
                user_input = input()
                cmd = user_input.strip().lower()
                if cmd == "q":
                    print("\nQuitting...")
                    quit_flag.set()
                    break
                elif cmd == "r":
                    print("\nRestarting server...")
                    # Ask for new port
                    try:
                        new_port_input = input(
                            f"Enter new port (or press Enter to keep {port}): "
                        ).strip()
                        if new_port_input:
                            new_port = int(new_port_input)
                            if 1024 <= new_port <= 65535:
                                port = new_port
                            else:
                                print(f"Invalid port {new_port}, keeping {port}")
                    except ValueError:
                        print(f"Invalid input, keeping port {port}")
                    restart_flag.set()
        except:
            pass

    # --------------------------------------------------
    # start input listener thread
    # --------------------------------------------------
    listener = threading.Thread(target=input_thread, daemon=True)
    listener.start()

    try:
        while not quit_flag.is_set():
            time.sleep(0.5)  # check every 500ms

            # Check for restart request
            if restart_flag.is_set():
                restart_flag.clear()
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Shutting down old server..."
                )
                if httpd:
                    httpd.shutdown()
                    httpd = None
                    server_thread = None

                print(f"[{datetime.now().strftime('%H:%M:%S')}] Re-rendering HTML...")
                render_html()

                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Starting new server on port {port}..."
                )
                if start_server():
                    try:
                        webbrowser.open(f"http://localhost:{port}/{output_file}")
                    except:
                        pass
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] Server restarted successfully!"
                    )
                else:
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] Failed to restart server"
                    )
                continue

            try:
                current_mtime = os.path.getmtime(template_path)
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] Template changed, re-rendering..."
                    )
                    render_html()
            except FileNotFoundError:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Warning: Template file was deleted!"
                )
                time.sleep(1)
                continue

    except KeyboardInterrupt:
        print("\n\nShutting down...")

    if httpd:
        httpd.shutdown()
    print("Goodbye!")
    sys.exit(0)
