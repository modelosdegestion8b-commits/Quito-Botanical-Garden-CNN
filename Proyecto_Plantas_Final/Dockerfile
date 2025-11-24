FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt requirements.txt

# Instalar NumPy explícitamente antes de las demás dependencias
RUN pip install --no-cache-dir numpy==2.0.2 && pip install --no-cache-dir -r requirements.txt -f https://download.pytorch.org/whl/torch_stable.html

COPY . .
EXPOSE 8080

CMD ["python", "app.py"]
COPY templates/ /app/templates/