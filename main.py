import os
import pandas as pd
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask
app = Flask(__name__)

try:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
except ValueError:
    print("ADVERTENCIA: No se pudo inicializar Firebase Admin SDK. ¿Ejecutando localmente sin credenciales?")
    pass

db = firestore.client()
# ---------------------------------

@app.route('/')
def ejecutar_extraccion():
    """
    Función principal que se ejecuta cuando Cloud Run recibe una petición.
    """
    # URL de la tabla de Sta. Clara
    url = "https://www.imn.ac.cr/especial/tablas/staclara.html"

    try:
        tablas = pd.read_html(url)
        print(f"Se encontraron {len(tablas)} tablas en la página.")
    except Exception as e:
        print(f"Error al leer la URL: {e}")
        return f"Error al leer la URL: {e}", 500

    tabla_actuales = None
    tabla_horarios = None

    for tabla in tablas:
        column_str = "".join(str(col) for col in tabla.columns)
        if any(col in column_str for col in ['Vmax', 'SUM_lluv', 'LLUV_ayer']):
            tabla_actuales = tabla.copy()
            print("-> Identificada como tabla de DATOS ACTUALES")
        elif len(tabla) > 5:
            tabla_horarios = tabla.copy()
            print("-> Identificada como tabla de HORARIOS")

    timestamp_extraccion = datetime.now()

    # Procesar y guardar tabla de datos actuales
    if tabla_actuales is not None:
        tabla_actuales.columns = [str(c).strip() for c in tabla_actuales.columns]
        datos_actuales_dict = tabla_actuales.to_dict('records')[0]
        datos_actuales_dict['timestamp_extraccion'] = timestamp_extraccion
        doc_id = timestamp_extraccion.strftime('%Y-%m-%d_%H-%M-%S')
        db.collection('datos_actuales').document(doc_id).set(datos_actuales_dict)
        print(f"Guardados datos actuales en Firestore con ID: {doc_id}")

    # Procesar y guardar tabla de horarios
    if tabla_horarios is not None:
        tabla_horarios.columns = [str(c).strip() for c in tabla_horarios.columns]
        if 'Temp' in tabla_horarios.columns:
            tabla_horarios["Temp"] = pd.to_numeric(tabla_horarios["Temp"], errors='coerce') / 100
        
        for index, row in tabla_horarios.iterrows():
            dato_horario_dict = row.to_dict()
            dato_horario_dict['timestamp_extraccion_lote'] = timestamp_extraccion
            hora_registro = str(row.get('Hora', index))
            doc_id = timestamp_extraccion.strftime('%Y-%m-%d') + f"_{hora_registro}"
            db.collection('datos_horarios').document(doc_id).set(dato_horario_dict, merge=True)
        print(f"Guardados {len(tabla_horarios)} registros horarios en Firestore.")

    print("Extracción completada exitosamente.")
    return "OK", 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))