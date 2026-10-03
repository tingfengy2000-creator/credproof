"""Start the candidate single page; real inference remains a separate explicit action."""
import argparse
from .web import Application, Server
from .presentation import install_demonstrations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--demo', action='store_true', help='Open curated real history, clearly labelled REPLAY')
    parser.add_argument('--mode', choices=['view', 'recheck', 'live'], default='view',
                        help='view: history only; recheck: isolation, no model; live: local model required')
    args = parser.parse_args()
    app = Application(access_mode=args.mode)
    if args.demo:
        install_demonstrations(app)
    with Server(('127.0.0.1', args.port), app) as server:
        print(f'CredProof: http://127.0.0.1:{server.server_address[1]}', flush=True)
        print('Curated histories are REPLAY. Live inference requires a ready local runtime.', flush=True)
        print(f'Mode: {args.mode}. Stop this server with Ctrl+C in this terminal.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
