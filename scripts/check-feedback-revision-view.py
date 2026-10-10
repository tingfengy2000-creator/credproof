"""Read an installed linked revision over loopback HTTP; never starts inference."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
import threading
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--method', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import agent_pilot.web as web
    import credproof_safety.agent as agent
    import agent_pilot.bounded_patch as bounded
    import agent_pilot.output_format as formatter
    assert sys.flags.isolated and all('site-packages' in m.__file__ for m in (web, agent, bounded, formatter))
    app = web.Application(root=args.data, histories=[args.method], access_mode='view')
    identifier = next(iter(app.runs))
    server = web.Server(('127.0.0.1', 0), app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://127.0.0.1:%s/api/agent/runs/%s' % (server.server_port, identifier), timeout=10) as response:
            body = json.load(response)
            status = response.status
        assert body['mode'] == 'REPLAY'
        assert body['display_label'] == '基于历史候选的新反馈修订'
        assert body['parent_task_id'] == 'live-c5e9217f868f4681a94bdda49c914e6e'
        assert body['model']['calls'] == 1 and body['validation']['verdict'] == 'FAIL'
        record = {'kind': 'INSTALLED_HISTORY_VIEW_HTTP_CHECK', 'new_model_calls': 0,
                  'dynamic_candidate_checks': 0, 'http_status': status, 'response': body,
                  'interpreter': sys.executable, 'isolated': True,
                  'version': importlib.metadata.version('credproof-safety'),
                  'modules': {m.__name__: m.__file__ for m in (web, agent, bounded, formatter)}}
        args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        print(json.dumps({'http_status': status, 'mode': body['mode'], 'verdict': body['validation']['verdict'],
                          'label': body['display_label'], 'new_model_calls': 0}, ensure_ascii=False))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
