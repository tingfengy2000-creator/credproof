"""Start the candidate single page; real inference remains a separate explicit action."""
import argparse
from pathlib import Path
from .web import Application, Server
from .presentation import install_demonstrations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--demo', action='store_true', help='Open curated real history, clearly labelled REPLAY')
    parser.add_argument('--workspace', type=Path, help='Candidate source/material directory (installed wheel may use an extracted package)')
    parser.add_argument('--history', type=Path, action='append', default=[], help='Explicit registered historical method under workspace/runs')
    parser.add_argument('--project-config', type=Path, help='Local operator explicitly authorizes one adapted project config; not accepted through HTTP')
    parser.add_argument('--mode', choices=['view', 'recheck', 'live'], default='view',
                        help='view: history only; recheck: isolation, no model; live: local model required')
    args = parser.parse_args()
    options = {'access_mode': args.mode, 'project_config': args.project_config, 'project_examples': args.demo, 'histories':args.history}
    if args.workspace:
        options['root'] = args.workspace.resolve(strict=True)
    app = Application(**options)
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
