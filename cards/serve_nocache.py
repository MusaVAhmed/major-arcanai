#!/usr/bin/env python3
"""Static server that refuses to be cached.

python -m http.server sends only Last-Modified, and Chrome on Android will
reuse a cached copy without revalidating. That cost a full phone run: the
handset re-ran an old reader_bench.html and produced byte-identical output to
the previous run, which looked like a fix that had not worked rather than a
fix that had never arrived.
"""
import http.server, socketserver, sys

class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8642
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('0.0.0.0', port), NoCache) as httpd:
        httpd.serve_forever()
