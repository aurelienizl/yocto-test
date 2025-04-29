# app.py
import datetime
import signal
import sys
import time
from flask import Flask, request, render_template, jsonify, Response, stream_with_context
from db import db
from job_queue import job_queue, Job

app = Flask(__name__, template_folder='templates', static_folder='static')

def _shutdown_handler(signum, frame):
    print(f"[{datetime.datetime.utcnow().isoformat()}] Shutdown signal {signum}", file=sys.stderr)
    job_queue.shutdown()
    sys.exit(0)

signal.signal(signal.SIGINT,  _shutdown_handler)
signal.signal(signal.SIGTERM, _shutdown_handler)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/enqueue', methods=['POST'])
def enqueue():
    git_uri = request.form.get('git_uri', '').strip()
    if not git_uri:
        return jsonify({ 'error': 'No Git URI provided' }), 400
    job = job_queue.add_job( Job(git_uri) )
    return jsonify({ 'message': 'Job enqueued', 'job_id': job.id })

@app.route('/tasks', methods=['GET'])
def list_tasks():
    tasks = db.get_tasks()
    return jsonify(tasks)

@app.route('/kill', methods=['POST'])
def kill_job():
    success, msg = job_queue.kill_current_job()
    return (jsonify({ 'message': msg }), 200) if success else (jsonify({ 'error': msg }), 400)

@app.route('/remove', methods=['POST'])
def remove_job():
    job_id = request.form.get('job_id', '').strip()
    if not job_id:
        return jsonify({ 'error': 'No job ID provided' }), 400
    success, msg = job_queue.remove_job(job_id)
    return (jsonify({ 'message': msg }), 200) if success else (jsonify({ 'error': msg }), 400)

@app.route('/logs/<job_id>')
def get_logs(job_id):
    rows = db.get_logs(job_id)
    if rows is None:
        return 'Job not found.', 404
    text = '\n'.join(f"[{r['timestamp']}] {r['line']}" for r in rows)
    return Response(text, mimetype='text/plain')

@app.route('/stream_logs/<job_id>')
def stream_logs(job_id):
    def gen():
        last_id = 0
        sent_any = False
        while True:
            rows = db.get_logs_since(job_id, last_id)
            if not rows and not sent_any:
                yield "data: [No logs to display...]\n\n"
                sent_any = True
            for r in rows:
                yield f"data: [{r['timestamp']}] {r['line']}\n\n"
                last_id = r['id']
                sent_any = True
            time.sleep(1)

    return Response(stream_with_context(gen()), mimetype='text/event-stream',
                    headers={
                      'Cache-Control': 'no-cache',
                      'Connection': 'keep-alive',
                      'X-Accel-Buffering':'no'
                    })

@app.route('/current')
def current_job():
    cj = job_queue.current_job
    if cj:
        return jsonify({'id': cj.id, 'git_uri': cj.git_uri, 'status': cj.status})
    return jsonify({'message': 'No job is currently running.'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)