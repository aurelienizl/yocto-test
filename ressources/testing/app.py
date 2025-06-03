import os
import logging
from flask import Flask, render_template
from endpoints import create_endpoints

def create_app():
    # Flask setup
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static'
    )

    # Simple logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
    )

    # Base directory from env or ./files
    base_dir = os.environ.get(
        'FOLDER_SERVE',
        os.path.join(os.getcwd(), '/home')
    )
    os.makedirs(base_dir, exist_ok=True)

    # Register our API
    create_endpoints(app, base_dir)

    @app.route('/')
    def index():
        return render_template('index.html')

    return app

if __name__ == '__main__':
    create_app().run(debug=True)
