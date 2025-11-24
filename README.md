# Quito-Botanical-Garden-CNN
Clasificación de plantas con Flask y TensorFlow en Google Cloud Run

# 🌿 Identificación de Flora del Jardín Botánico de Quito con CNN

### Descripción del Proyecto
Este proyecto implementa una solución de **Visión por Computadora (Computer Vision)** basada en Redes Neuronales Convolucionales (CNN) para identificar 110 especies de plantas endémicas y exóticas presentes en el Jardín Botánico de Quito.

El sistema fue concebido como una herramienta educativa gamificada para resolver la desconexión de los jóvenes con la botánica. A diferencia de las apps tradicionales, esta solución se desplegó como una **Web App escalable en la nube**, permitiendo acceso inmediato.

### 🚀 Impacto y Resultados
* **Usuarios Activos:** +400 visitantes utilizaron la herramienta en el jardín.
* **Accesibilidad:** Despliegue en nube (Serverless) que permitió soportar picos de tráfico sin caída del servicio.
* **Precisión:** Clasificación efectiva de 110 clases botánicas complejas.

### 🛠️ Tecnologías Utilizadas
* **Lenguaje:** Python 3.x
* **Web Framework:** Flask (Backend API)
* **Deep Learning:** TensorFlow / Keras
* **Infraestructura:** Google Cloud Run (Serverless) & Docker
* **Procesamiento de Imágenes:** PIL / OpenCV

### 📂 Estructura del Proyecto
* `entrenamiento_cnn.ipynb`: Notebook de entrenamiento del modelo.
* `app.py`: Código principal de la aplicación web (Backend).
* `Dockerfile`: Configuración para la creación del contenedor en Cloud Run.
* `requirements.txt`: Dependencias y librerías necesarias.

### ☁️ Despliegue en Google Cloud Run
El modelo no corre localmente en el dispositivo del usuario, sino que fue "dockerizado" y subido a **Google Cloud Run**. Esto permite:
1.  El usuario sube la foto desde la interfaz web.
2.  La imagen viaja a la nube, donde el contenedor procesa la inferencia.
3.  El resultado retorna al usuario en milisegundos.

---
**Autor:** Daniel Pacheco
*Data Scientist & Business Analytics Specialist*
[LinkedIn](https://www.linkedin.com/in/daniel-pacheco93)
