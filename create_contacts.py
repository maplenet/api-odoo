import requests
import random
import string
import time

# URL de la API para crear contacto
url_crear = "http://127.0.0.1:8000/create_contact"
# URL de la API para eliminar contacto
url_eliminar = "http://127.0.0.1:8000/contact/{id}"

# Función para generar un nombre aleatorio
def generar_nombre():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=30))

# Función para generar datos aleatorios para el contacto
def generar_contacto():
    return {
        "name": generar_nombre(),
        "company_name": "Doe Enterprises",
        "is_company": True,
        "type": "contact",
        "street": "123 Main Street",
        "street2": "Suite 456",
        "city": "New York",
        "state_id": 1,
        "zip": "10001",
        "country_id": 233,
        "phone": "+123456789",
        "mobile": "+987654321",
        "email": "johndoe@example.com",
        "website": "https://www.doeenterprises.com",
        "vat": "US123456789",
        "lang": "en_US",
        "comment": "This is a test comment.",
        "customer_rank": 1,
        "supplier_rank": 0,
        "credit_limit": 10000.0,
        "user_id": 2,
        "parent_id": 1,
        "category_id": [1, 2, 3],
        "function": "CEO",
        "title": 1,
        "industry_id": 1,
        "team_id": 1,
        "property_payment_term_id": 1,
        "property_supplier_payment_term_id": 2
    }

# Función para crear contactos
def crear_contactos(cantidad):
    ids_creados = []
    inicio = time.time()  # Captura el tiempo de inicio

    for _ in range(cantidad):
        response = requests.post(url_crear, json=generar_contacto())
        
        # Verificar el contenido de la respuesta
        print(f"Respuesta de la API al crear: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            # Ahora buscamos el campo 'contact_id' en la respuesta
            if 'contact_id' in data:
                ids_creados.append(data['contact_id'])
            else:
                print(f"contact_id no encontrado en la respuesta: {data}")
        else:
            print(f"Error creando contacto: {response.status_code}")

    fin = time.time()  # Captura el tiempo de fin
    tiempo_total = fin - inicio  # Tiempo total de ejecución

    return ids_creados, tiempo_total

# Función para eliminar contactos
def eliminar_contactos(ids):
    inicio = time.time()  # Captura el tiempo de inicio

    for id_contacto in ids:
        response = requests.delete(url_eliminar.format(id=id_contacto))
        
        # Verificar el contenido de la respuesta
        print(f"Respuesta de la API al eliminar (ID {id_contacto}): {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') == True:
                print(f"Contacto {id_contacto} eliminado correctamente.")
            else:
                print(f"Error al eliminar contacto {id_contacto}: {data}")
        else:
            print(f"Error al eliminar contacto {id_contacto}: {response.status_code}")

    fin = time.time()  # Captura el tiempo de fin
    tiempo_total = fin - inicio  # Tiempo total de ejecución

    return tiempo_total

# Solicitar la cantidad de registros
cantidad = int(input("¿Cuántos contactos deseas crear? "))

# Crear los contactos y obtener los resultados
ids, tiempo_creacion = crear_contactos(cantidad)



# Eliminar los contactos creados y medir el tiempo
tiempo_eliminacion = eliminar_contactos(ids)

# Mostrar los resultados de la creación
print(f"Contactos creados: {ids}")
# Cantidades de contactos creados
print(f"Cantidad de contactos creados: {len(ids)}")

print(f"Tiempo total de ejecución para crear: {tiempo_creacion:.2f} segundos")

# Mostrar el tiempo total para eliminación
print(f"Tiempo total de ejecución para eliminar: {tiempo_eliminacion:.2f} segundos")
