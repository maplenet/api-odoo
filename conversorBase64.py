from PIL import Image
import base64
import io

# Ruta de la imagen original
input_image_path = "images/foto1.jpg"

# Redimensionar y reducir calidad
def resize_and_compress_image(input_path, max_width=200, max_height=200, quality=30):
    with Image.open(input_path) as img:
        # Mantener proporción al redimensionar
        img.thumbnail((max_width, max_height))
        # Crear un buffer en memoria para guardar la imagen procesada
        buffer = io.BytesIO()
        img.save(buffer, format="jpeg", quality=quality)  # Usar formato jpeg
        buffer.seek(0)
        return buffer

# Convertir la imagen procesada a Base64
def image_to_base64(image_buffer):
    return base64.b64encode(image_buffer.read()).decode("utf-8")

# Procesar imagen y convertir a Base64
image_buffer = resize_and_compress_image(input_image_path)
base64_image = image_to_base64(image_buffer)

print(base64_image)
