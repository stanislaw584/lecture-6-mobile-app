# Test cloud (like Firebase REST: GET / PUT one JSON)
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

data = None


class Handler(BaseHTTPRequestHandler):
    def reply(self):
        body = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply()

    def do_PUT(self):
        global data
        size = int(self.headers['Content-Length'])
        data = json.loads(self.rfile.read(size))
        self.reply()


HTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
