import sqlite3

# registro de codigos

# def query_verification():
#     # Conectar a la base de datos (se asume que verification.db está en el mismo directorio)
#     connection = sqlite3.connect("verification.db")
#     cursor = connection.cursor()

#     # Ejecutar la consulta para obtener todos los registros de la tabla verification
#     cursor.execute("SELECT * FROM verification")
#     rows = cursor.fetchall()

#     # Cerrar la conexión
#     connection.close()

#     # Mostrar los resultados
#     if rows:
#         print("Registros en la tabla 'verification':")
#         for row in rows:
#             print(row)
#     else:
#         print("No se encontraron registros en la tabla 'verification'.")

# if __name__ == '__main__':
#     query_verification()

# -----------------------------------------------------------        


# registro de usuarios

# def query_users():
#     # Conectar a la base de datos (se asume que verification.db está en el mismo directorio)
#     connection = sqlite3.connect("verification.db")
#     cursor = connection.cursor()

#     # Ejecutar la consulta para obtener todos los registros de la tabla users
#     cursor.execute("SELECT * FROM users")
#     rows = cursor.fetchall()

#     # Cerrar la conexión
#     connection.close()

#     # Mostrar los resultados
#     if rows:
#         print("Registros en la tabla 'users':")
#         for row in rows:
#             print(row)
#     else:
#         print("No se encontraron registros en la tabla 'users'.")

# if __name__ == '__main__':
#     query_users()

# -----------------------------------------------------------        

# funciona para obtener los registros de la tabla tokens
def query_tokens():
    # Conectar a la base de datos (se asume que verification.db está en el mismo directorio)
    connection = sqlite3.connect("verification.db")
    cursor = connection.cursor()

    # Ejecutar la consulta para obtener todos los registros de la tabla tokens
    cursor.execute("SELECT * FROM tokens")
    rows = cursor.fetchall()

    # Cerrar la conexión
    connection.close()

    # Mostrar los resultados
    if rows:
        print("Registros en la tabla 'tokens':")
        for row in rows:
            print(row)
    else:
        print("No se encontraron registros en la tabla 'tokens'.")

if __name__ == '__main__':
    query_tokens()

