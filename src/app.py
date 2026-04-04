import sys
import os

# Garante que o diretório src está no path
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask
from database.schema import create_tables
from routes.escola_routes import escola_bp
from routes.dashboard_routes import dashboard_bp

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')

app.secret_key = 'horario_escolar_secret_2024'

# Registra blueprints
app.register_blueprint(escola_bp)
app.register_blueprint(dashboard_bp)

if __name__ == '__main__':
    create_tables()
    print("=" * 50)
    print("  Sistema de Horários Escolares")
    print("  Acesse: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
