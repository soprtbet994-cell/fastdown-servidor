import os, re, glob, shutil, tempfile
from flask import Flask, request, jsonify, send_file, abort, after_this_request
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)
OK = re.compile(r'^https?://([a-z0-9-]+\.)*(youtube\.com|youtu\.be|facebook\.com|fb\.watch|instagram\.com)/', re.I)
MAX_SEG = 15 * 60  # videos de hasta 15 min

def opts(extra=None):
    o = {'quiet': True, 'noplaylist': True, 'socket_timeout': 20}
    cf = os.environ.get('COOKIES_FILE')
    if cf and os.path.exists(cf):
        o['cookiefile'] = cf
    o.update(extra or {})
    return o

def check(url):
    if not OK.match(url or ''):
        abort(400, 'Enlace no permitido')

@app.get('/')
def home():
    return 'FastDown server OK'

@app.get('/info')
def info():
    url = request.args.get('url', '')
    check(url)
    try:
        with yt_dlp.YoutubeDL(opts({'skip_download': True})) as y:
            d = y.extract_info(url, download=False)
    except Exception as e:
        return jsonify(error=str(e)[:200]), 422
    if (d.get('duration') or 0) > MAX_SEG:
        return jsonify(error='El video es muy largo (máx. 15 min)'), 422
    return jsonify(title=d.get('title'), cover=d.get('thumbnail'), author=d.get('uploader'))

@app.get('/dl')
def dl():
    url, q = request.args.get('url', ''), request.args.get('q', 'hd')
    check(url)
    fmt = {'hd': 'bv*[height<=1080]+ba/b[height<=1080]/b',
           'sd': 'bv*[height<=480]+ba/b[height<=480]/b',
           'au': 'ba/b'}.get(q, 'b')
    tmp = tempfile.mkdtemp()
    o = opts({'format': fmt, 'outtmpl': tmp + '/v.%(ext)s', 'merge_output_format': 'mp4',
              'max_filesize': 250 * 1024 * 1024})
    if q == 'au':
        o['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]

    @after_this_request
    def limpiar(r):
        shutil.rmtree(tmp, ignore_errors=True)
        return r
    try:
        with yt_dlp.YoutubeDL(o) as y:
            y.download([url])
        f = glob.glob(tmp + '/v.*')[0]
    except Exception as e:
        return jsonify(error=str(e)[:200]), 422
    return send_file(f, as_attachment=True, download_name='fastdown.' + f.rsplit('.', 1)[1])
