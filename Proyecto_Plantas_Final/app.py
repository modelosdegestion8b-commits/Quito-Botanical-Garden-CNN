import os
import pickle
import json
import psycopg2
from flask import Flask, request, render_template, send_from_directory, jsonify
import torch
from torchvision.models import resnet50
from torchvision import transforms
from PIL import Image
from google.cloud import storage
from torch import nn
import firebase_admin
from firebase_admin import credentials, auth

app = Flask(__name__, static_folder="static")

# 🔹 Configuración
BUCKET_NAME = "buketrecuperadojbq"
MODEL_FILE = "modelo_resnet50.pth"
CLASSES_FILE = "clases.pkl"
JSON_FILE = "plantas.json"

# 🔹 Inicialización de Firebase (CORREGIDO)
# Intenta usar variables de entorno primero (para Cloud Run), sino busca el archivo local
firebase_cred_path = os.getenv("FIREBASE_CREDENTIALS", "firebase_credentials.json")

try:
    if os.path.exists(firebase_cred_path):
        cred = credentials.Certificate(firebase_cred_path)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase inicializado con archivo local.")
    else:
        # Si no hay archivo, asume que estamos en Cloud Run y usa las credenciales por defecto
        firebase_admin.initialize_app()
        print("✅ Firebase inicializado con credenciales por defecto (Cloud).")
except ValueError:
    # Evita el error si Firebase ya estaba inicializado
    print("⚠️ Firebase ya estaba inicializado.")

# 🔹 Función para descargar archivos desde Google Cloud Storage
def descargar_archivo(bucket_name, file_name, local_path):
    if not os.path.exists(local_path): # Solo descarga si no existe
        try:
            client = storage.Client()
            bucket = client.get_bucket(bucket_name)
            blob = bucket.blob(file_name)
            blob.download_to_filename(local_path)
            print(f"📥 Archivo {file_name} descargado.")
        except Exception as e:
            print(f"❌ Error al descargar {file_name}: {e}")

# Descargar archivos necesarios al inicio
descargar_archivo(BUCKET_NAME, MODEL_FILE, MODEL_FILE)
descargar_archivo(BUCKET_NAME, CLASSES_FILE, CLASSES_FILE)
descargar_archivo(BUCKET_NAME, JSON_FILE, JSON_FILE)

# 🔹 Cargar Modelo y Recursos
try:
    model = resnet50()
    model.fc = nn.Linear(2048, 110)
    if os.path.exists(MODEL_FILE):
        model.load_state_dict(torch.load(MODEL_FILE, map_location=torch.device('cpu')))
        model.eval()
        print("✅ Modelo cargado.")
    else:
        print("⚠️ Advertencia: No se encontró el archivo del modelo.")
except Exception as e:
    print(f"❌ Error al cargar el modelo: {e}")

try:
    with open(CLASSES_FILE, "rb") as f:
        class_names = pickle.load(f)
except Exception:
    class_names = []
    print("⚠️ Advertencia: No se pudieron cargar las clases.")

try:
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        plantas_info = json.load(f)
    plantas_info = {k.lower(): v for k, v in plantas_info.items()}
except Exception:
    plantas_info = {}
    print("⚠️ Advertencia: No se pudo cargar el JSON de plantas.")

# 🔹 Transformación para las imágenes
transform_val = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
])

# ================= RUTAS =================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/navegacion')
def navegacion():
    return render_template('navegacion.html')

@app.route('/pagina_juego')
def pagina_juego():
    return render_template('pagina_juego.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/api/plantas', methods=['GET'])
def obtener_plantas():
    return jsonify(plantas_info)

@app.route('/api/analizar_foto', methods=['POST'])
def analizar_foto():
    if 'imagen' not in request.files or 'planta_esperada' not in request.form:
        return jsonify({'error': 'Faltan datos'}), 400

    archivo = request.files['imagen']
    planta_esperada = request.form['planta_esperada'].lower()

    try:
        img = Image.open(archivo.stream).convert('RGB')
        img_tensor = transform_val(img).unsqueeze(0)
        with torch.no_grad():
            outputs = model(img_tensor)
            confidences = torch.nn.functional.softmax(outputs[0], dim=0)
            prob, predicted_idx = torch.max(confidences, dim=0)
            nombre_clase = class_names[predicted_idx.item()]
            
            # Procesamiento del nombre
            partes = nombre_clase.split("_")
            # Manejo de errores si el nombre no tiene el formato esperado
            if len(partes) >= 2:
                nombre_predicho = f"{partes[-2]} {partes[-1]}"
            else:
                nombre_predicho = nombre_clase

        def normalizar_nombre(nombre):
            return nombre.strip().lower().replace("%20", " ")

        resultado = {
            'planta_predicha': nombre_predicho,
            'confianza': round(prob.item() * 100, 2),
            'coincide': normalizar_nombre(nombre_predicho) == normalizar_nombre(planta_esperada)
        }
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/planta/<nombre_cientifico>')
def planta(nombre_cientifico):
    nombre_limpio = nombre_cientifico.replace('%20', ' ').strip().lower()
    info = plantas_info.get(nombre_limpio)

    if info:
        # Arreglar URLs de fotos
        if "fotos" in info:
            info["fotos"] = [
                f if f.startswith("http") else f"https://storage.googleapis.com/{BUCKET_NAME}/{f}" 
                for f in info["fotos"]
            ]
        return render_template('planta.html', nombre_cientifico=nombre_limpio, info=info)
    else:
        return f"<h2 style='color:red;'>Información no encontrada para {nombre_limpio}</h2>"

# ================= BASE DE DATOS & AUTH =================

def registrar_usuario(uid, nombre, email):
    # SEGURIDAD: Usamos os.getenv para no quemar contraseñas en el código
    db_host = os.getenv("DB_HOST", "localhost")
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASS", "tu_password_local") # se lo puede cambiar 
    db_name = os.getenv("DB_NAME", "jardincnn")
    
    try:
        conn = psycopg2.connect(dbname=db_name, user=db_user, password=db_pass, host=db_host)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO usuarios (id, nombre, email) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING;",
            (uid, nombre, email)
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ Usuario {nombre} registrado.")
    except Exception as e:
        print(f"❌ Error DB: {e}")

@app.route('/verificar_usuario', methods=['POST'])
def verificar_usuario():
    id_token = request.json.get('id_token')
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
        email = decoded_token["email"]
        nombre = decoded_token.get("name", "Usuario")
        
        # Intentar registrar en DB (si falla no detiene la app)
        registrar_usuario(uid, nombre, email)
        
        return jsonify({"uid": uid, "email": email, "name": nombre}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 401

@app.after_request
def liberar_recursos(response):
    # Solo limpiar caché si hay GPU (opcional en Cloud Run CPU)
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return response

# ================= EJECUCIÓN =================
# Esto SIEMPRE va al final, no se porque pero solo asi funciona jejeje
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

##esto esta ducado y causa errores 

# firebase_admin.initialize_app(cred)

