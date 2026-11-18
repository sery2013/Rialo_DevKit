"""Synthetic JSON-RPC server for local SDK integration tests, not a Rialo node."""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

log_path = sys.argv[1]

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with open(log_path, 'a', encoding='utf-8') as log:
            log.write(json.dumps(body) + '\n')
        if body['method'] == 'getBalance':
            result = {'context': {'slot': 1}, 'value': 1500000000}
        elif body['method'] == 'getLatestBlockhash':
            result = {'context': {'slot': 1}, 'value': {'blockhash': '1' * 32, 'lastValidBlockHeight': 100}}
        elif body['method'] == 'sendTransaction':
            result = '1' * 64
        else:
            self.send_error(400); return
        payload = json.dumps({'jsonrpc': '2.0', 'id': body['id'], 'result': result}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args): pass

server = HTTPServer(('127.0.0.1', 0), Handler)
print(server.server_port, flush=True)
server.serve_forever()
