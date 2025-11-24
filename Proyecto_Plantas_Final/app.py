import os
import pickle
import json
from flask import Flask, request, render_template
import torch
from torchvision.models import resnet50
from torchvision import transforms
from PIL import Image
from google.cloud import storage
from torch import nn
from flask import send_from_directory
from flask import Flask, render_template, send_from_directory
from flask import Flask, render_template, url_for
from flask import Flask, jsonify
app = Flask(__name__, static_folder="static")

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# 🔹 Función para descargar archivos desde Google Cloud Storage
def descargar_archivo(bucket_name, file_name, local_path):
    try:
        client = storage.Client()
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.download_to_filename(local_path)
        print(f"Archivo {file_name} descargado en {local_path}")
    except Exception as e:
        print(f"Error al descargar {file_name} desde {bucket_name}: {e}")
        exit(1)

# 🔹 Configuración del bucket en Google Cloud Storage
BUCKET_NAME = "buketrecuperadojbq"
MODEL_FILE = "modelo_resnet50.pth"
CLASSES_FILE = "clases.pkl"
JSON_FILE = "plantas.json"

# 🔹 Descargar archivos necesarios
descargar_archivo(BUCKET_NAME, MODEL_FILE, MODEL_FILE)
descargar_archivo(BUCKET_NAME, CLASSES_FILE, CLASSES_FILE)
descargar_archivo(BUCKET_NAME, JSON_FILE, JSON_FILE)

# 🔹 Cargar el modelo ResNet50 con la estructura correcta
try:
    model = resnet50()
    model.fc = nn.Linear(2048, 110)  # Ajustar para 110 clases
    model.load_state_dict(torch.load(MODEL_FILE, map_location=torch.device('cpu')))
    model.eval()
    print("Modelo cargado exitosamente.")
except Exception as e:
    print(f"Error al cargar el modelo: {e}")
    exit(1)

# 🔹 Cargar las clases desde el archivo .pkl
try:
    with open(CLASSES_FILE, "rb") as f:
        class_names = pickle.load(f)
    print("Clases cargadas exitosamente.")
except Exception as e:
    print(f"Error al cargar las clases: {e}")
    exit(1)

# 🔹 Cargar el JSON de plantas y normalizar nombres científicos
try:
    with open(JSON_FILE, "r") as f:
        plantas_info = json.load(f)
    plantas_info = {k.lower(): v for k, v in plantas_info.items()}  # Convertir claves a minúsculas
    print("JSON de plantas cargado exitosamente.")
except Exception as e:
    print(f"Error al cargar plantas.json: {e}")
    exit(1)

# 🔹 Transformación utilizada en el modelo
transform_val = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
])

# 🔹 Página principal
@app.route('/')
def index():
    return render_template('index.html')

# 🔹 Página de navegación
@app.route('/navegacion')
def navegacion():
    return render_template('navegacion.html')

## Pagina de juego from flask import Flask, render_template
@app.route('/pagina_juego')
def pagina_juego():
    return render_template('pagina_juego.html')
##ruta que exponga el json al fornted
@app.route('/api/plantas', methods=['GET'])
def obtener_plantas():
    try:
        with open("plantas.json", "r", encoding="utf-8") as f:
            plantas = json.load(f)
        return jsonify(plantas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

## API pagina de juego y modificadores para al camara y deteccion de especies
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
            partes = nombre_clase.split("_")
            nombre_predicho = f"{partes[-2]} {partes[-1]}"  # Extrae solo el nombre cientfico y no todo el dato biologico

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
 
# 🔹 Predicción de imagen con el modelo
@app.route('/predict', methods=['POST'])
def predict():
    if 'file' not in request.files:
        return "<h2 style='color:red;'>Error: No se encontró el archivo</h2>"

    file = request.files['file']
    if file.filename == '':
        return "<h2 style='color:red;'>Error: El archivo no tiene nombre</h2>"

    try:
        img = Image.open(file).convert('RGB')
    except Exception as e:
        return f"<h2 style='color:red;'>Error: No se pudo procesar la imagen ({e})</h2>"

    # Aplicar transformación
    img_tensor = transform_val(img).unsqueeze(0)

    # Predicción con el modelo
    try:
        with torch.no_grad():
            output = model(img_tensor)
            probabilities = torch.nn.functional.softmax(output[0], dim=0).tolist()

        # Obtener las 3 predicciones con mayor probabilidad
        top3_indices = sorted(range(len(probabilities)), key=lambda i: probabilities[i], reverse=True)[:3]
        top3_predictions = []
        for idx in top3_indices:
            taxon_data = class_names[idx].split("_")
            top3_predictions.append({
                'reino': taxon_data[1],
                'filo': taxon_data[2],
                'clase': taxon_data[3],
                'orden': taxon_data[4],
                'familia': taxon_data[5],
                'genero': taxon_data[6],
                'especie': taxon_data[7],
                'scientific_name': f"{taxon_data[6]} {taxon_data[7]}",
                'probability': probabilities[idx] * 100
            })

        return render_template('template.html', predictions=top3_predictions)
    except Exception as e:
        return f"<h2 style='color:red;'>Error en la predicción: {e}</h2>"



# 🔹 Ver información de una planta
@app.route('/planta/<nombre_cientifico>')
def planta(nombre_cientifico):
    nombre_cientifico_decodificado = nombre_cientifico.replace('%20', ' ').strip().lower()
    planta_info = plantas_info.get(nombre_cientifico_decodificado, None)

    if planta_info:
        # Construir URL de la imagen correctamente
        BUCKET_NAME = "buketrecuperadojbq"
        if "fotos" in planta_info:
            planta_info["fotos"] = [foto if foto.startswith("https://storage.googleapis.com") else f"https://storage.googleapis.com/{BUCKET_NAME}/{foto}" for foto in planta_info["fotos"]]

        return render_template('planta.html', nombre_cientifico=nombre_cientifico_decodificado, info=planta_info)
    else:
        return f"<h2 style='color:red;'>Lo sentimos, aún no tenemos información sobre {nombre_cientifico_decodificado}</h2>"
# 🔹 Liberar memoria después de cada solicitud
@app.after_request
def liberar_recursos(response):
    torch.cuda.empty_cache()
    return response

# 🔹 Ejecutar la aplicación en el puerto requerido por Google Cloud Run
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # ✅ Definir el puerto correctamente
    app.run(host="0.0.0.0", port=port)  # ✅ Exponer la app en el puerto 8080

import firebase_admin
from firebase_admin import credentials, auth

# Cargar credenciales desde el archivo JSON
cred = credentials.Certificate("C:/Users/USUARIO/De Salida/jbqloging-firebase-adminsdk-fbsvc-4aa3365d6c.json")
firebase_admin.initialize_app(cred)

## Verificacion del usuario
@app.route('/verificar_usuario', methods=['POST'])
def verificar_usuario():
    id_token = request.json.get('id_token')  # Recibe el token desde el frontend
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
        email = decoded_token["email"]
        nombre = decoded_token.get("name", "Usuario desconocido")

        # Registrar usuario en PostgreSQL
        registrar_usuario(uid, nombre, email)

        return jsonify({"uid": uid, "email": email, "name": nombre}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 401





import psycopg2  # Necesario para conectar con PostgreSQL

def registrar_usuario(uid, nombre, email):
    try:
        conn = psycopg2.connect(
            dbname="jardincnn", user="TU_USUARIO", password="TU_PASSWORD", host="TU_HOST"
        )
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO usuarios (id, nombre, email) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING;",
            (uid, nombre, email)
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ Usuario {nombre} registrado correctamente en PostgreSQL.")
    except psycopg2.Error as e:
        print(f"❌ Error al registrar usuario en PostgreSQL: {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if os.environ.get("FIREBASE_CONFIG"):
    cred_dict = json.loads(os.environ.get("FIREBASE_CONFIG"))
    cred = credentials.Certificate(cred_dict)
else:
    cred = credentials.Certificate("C:/Users/USUARIO/De Salida/jbqloging-firebase-adminsdk-fbsvc-4aa3365d6c.json")  # Local

##esto esta ducado y causa errores 
# firebase_admin.initialize_app(cred)