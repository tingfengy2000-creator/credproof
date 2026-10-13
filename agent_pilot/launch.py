"""Start the candidate single page; real inference remains a separate explicit action."""
import argparse
import errno
import socket
import signal
import sys
import webbrowser
from pathlib import Path
from .web import Application, Server
from .presentation import install_demonstrations, install_review_demonstration, close_review_demonstration


def server_for(app, port, auto_port=False):
    try:
        return Server(('127.0.0.1', port), app)
    except OSError as error:
        occupied = error.errno == errno.EADDRINUSE
        # Windows exclusive listeners can report WSAEACCES, not WSAEADDRINUSE.
        # Confirm a listener before treating access denied as a busy port.
        if not occupied and getattr(error, 'winerror', None) == 10013:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                    occupied = True
            except OSError:
                pass
        if not auto_port or not occupied:
            raise
        return Server(('127.0.0.1', 0), app)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--auto-port', action='store_true', help='Use an available loopback port if the requested port is busy')
    parser.add_argument('--open-browser', action='store_true', help='Open the actual loopback address in the default browser')
    parser.add_argument('--demo', action='store_true', help='Open curated real history, clearly labelled REPLAY')
    parser.add_argument('--workspace', type=Path, help='Candidate source/material directory (installed wheel may use an extracted package)')
    parser.add_argument('--history', type=Path, action='append', default=[], help='Explicit registered historical method under workspace/runs')
    parser.add_argument('--project-config', type=Path, help='Local operator explicitly authorizes one adapted project config; not accepted through HTTP')
    parser.add_argument('--bench-results', type=Path, help='Read-only benchmark results file (bench-results/v1) for the dashboard')
    parser.add_argument('--mode', choices=['view', 'recheck', 'live'], default='view',
                        help='view: history only; recheck: isolation, no model; live: local model required')
    args = parser.parse_args()
    options = {'access_mode': args.mode, 'project_config': args.project_config, 'project_examples': args.demo, 'histories':args.history}
    if args.workspace:
        options['root'] = args.workspace.resolve(strict=True)
    bundled = Path(options.get('root', Path(__file__).resolve().parents[1])) / 'docs/bench/bench-results.json'
    if args.bench_results:
        options['bench_results'] = args.bench_results.resolve(strict=True)
    elif args.demo and bundled.is_file():
        options['bench_results'] = bundled
    app = Application(**options)
    previous_break = None
    try:
        if hasattr(signal, 'SIGBREAK'):
            def interrupt(signum, frame):
                raise KeyboardInterrupt
            previous_break = signal.signal(signal.SIGBREAK, interrupt)
        if args.demo:
            install_demonstrations(app)
            install_review_demonstration(app)
        server = server_for(app, args.port, args.auto_port)
        with server:
            url = f'http://127.0.0.1:{server.server_address[1]}'
            print(f'CredProof: {url}', flush=True)
            print('Curated histories and dev35 reviews are REPLAY; demo review edits are disposable.', flush=True)
            print(f'Mode: {args.mode}. Stop this server with Ctrl+C in this terminal.', flush=True)
            if args.open_browser:
                try:
                    if not webbrowser.open(url):
                        print('Browser did not open. Copy the address above into your browser.', flush=True)
                except webbrowser.Error:
                    print('Browser did not open. Copy the address above into your browser.', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    except OSError as error:
        print(f'CredProof could not start ({type(error).__name__}). Check temporary-folder write permission and the requested port; keep this window open for details.', file=sys.stderr)
        raise
    finally:
        try:
            close_review_demonstration(app)
        finally:
            if previous_break is not None:
                signal.signal(signal.SIGBREAK, previous_break)


if __name__ == '__main__':
    main()
