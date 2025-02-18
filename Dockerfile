# Usa una imagen base de Python 3.11 slim (más ligera)
FROM python:3.11-slim

# Establece el directorio de trabajo en la imagen
WORKDIR /app

# Copia el archivo de requerimientos primero para aprovechar la cache de Docker
COPY requirements.txt .

# Actualiza pip e instala las dependencias
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copia el resto del código del proyecto al contenedor
COPY . .

# Si tienes un archivo de entorno (.env), puedes copiarlo también:
# COPY .env .

# Exponer el puerto en el que la app se ejecutará (Uvicorn por defecto usa el 8000)
EXPOSE 8000

# Ejecuta el script para inicializar la base de datos.
# Nota: Si la base de datos ya fue creada o deseas ejecutarlo manualmente, puedes omitir esta línea.
# RUN python init_db.py

# Comando para iniciar la aplicación (sin --reload para producción)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]