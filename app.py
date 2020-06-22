#!/usr/bin/env python
'''
Monitor cardíaco
---------------------------
Autor: Inove Coding School
Version: 1.0
 
Descripcion:
Se utiliza Flask para crear un WebServer que levanta los datos de alquileres de inmuebles
y los presenta en un mapa distribuidos por ubicación
 
Ejecución: Lanzar el programa y abrir en un navegador la siguiente dirección URL
http://127.0.0.1:5000/

Nos deberá aparecer el mapa con los alquileres de la zona, identificados por color:
- Verde: Alquiler dentro del promedio en precio
- Amarillo: Alquiler debajo del promedio en precio
- Rojo: Alquiler por arribba del promedio en precio
- Azul: Alquiler en dolares US$

- Podremos también visualizar el análisis de los alquileres de la zona
http://127.0.0.1:5000/reporte

- Podremos visualizar la predicción de costo de alquiler basado
 en el algoritmo de inteligencia artificial implementado
http://127.0.0.1:5000/prediccion

Requisitos de instalacion:

- Python 3.x
- Libreriras (incluye los comandos de instalacion)
    pip install numpy
    pip install pandas
    pip install -U Flask
'''

__author__ = "Inove Coding School"
__email__ = "INFO@INOVE.COM.AR"
__version__ = "1.0"


import traceback
import io
import sys
import os
import base64
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
from flask import Flask, request, jsonify, render_template, Response, redirect
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

# Indico la carpeta en donde se encuentran los templates html
APP_PATH = os.path.dirname(os.path.realpath(__file__))
TEMPLATE_PATH = os.path.join(APP_PATH, 'templates')
TEMPLATE_PATH = os.path.join(TEMPLATE_PATH, 'monitor')

app = Flask(__name__, template_folder=TEMPLATE_PATH)


@app.route("/")
def index():
    return redirect('/monitor')


@app.route("/monitor")
def monitor():
    return render_template('index.html')


@app.route("/monitor/reset")
def reset():

    conn = sqlite3.connect('heartcare.db')
    c = conn.cursor()
    c.execute('''
                DROP TABLE IF EXISTS heartrate;
            ''')
    c.execute('''CREATE TABLE heartrate(
            [id] INTEGER PRIMARY KEY AUTOINCREMENT,
            [time] TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            [name] STRING NOT NULL,
            [value] INTEGER NOT NULL
            )
            ''')

    df = pd.read_csv('vikings_female_24.csv')
    df['time_seconds'] = np.arange(len(df))
    
    start_date_str = '2019-05-10 12:00:00'
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d %H:%M:%S')

    # Calculo la fecha de cada muestra utilizando la fecha de inicio sumado
    # a los segundos del ensayo
    df['time'] = df.apply(lambda x: start_date + timedelta(seconds=x['time_seconds']), axis=1)

    # Asigno a todos las filas el nombre de la persona
    df['name'] = 'vikings_female_24'

    # Renombro el nombre de la columna heart a value para que sea
    # compatible con la base de datos
    df.rename(columns={'heart':'value'}, inplace=True)
    
    # Extraigo los datos que almacenare en la base de datos y los persisto
    heartrate = df[ ['time', 'name', 'value'] ]
    heartrate.to_sql('heartrate', conn, if_exists='replace', index = False)

    # SQL Viewer
    # https://inloop.github.io/sqlite-viewer/#

    return redirect('/monitor')


@app.route('/monitor/registro', methods=['POST', 'GET'])
def registro():
    if request.method == 'GET':
        # Si entré por "GET" es porque acabo de cargar la página
        try:
            return render_template('registro.html')
        except:
            return jsonify({'trace': traceback.format_exc()})

    if request.method == 'POST':
        # Si entré por "POST" es porque se ha precionado el botón "Enviar"
        try:

            nombre = str(request.form.get('name'))
            pulsos = str(request.form.get('heart_rate'))

            if(nombre is None or pulsos is None or pulsos.isdigit() is False):
                # Datos ingresados incorrectos
                return Response(status = 200)

            # Ya que pandas tiene una interfaz comoda para exportar
            # un dataframe a SQL crearemos un dataframe con los datos
            # enviados desde la API
            columns = ['time', 'name', 'value']
            heartrate = pd.DataFrame(columns=columns)
            heartrate = heartrate.append({
                                        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        'name': nombre,
                                        'value': int(pulsos)},
                                        ignore_index=True)

            # Persisto lo datos en la base de datos
            conn = sqlite3.connect('heartcare.db')
            heartrate.to_sql('heartrate', conn, if_exists='append', index = False)

            # Busco todos los registros de ritmo cardíaco realizados a nombre
            # de la persona
            query = 'select time,value from heartrate WHERE name = "{}"'.format(nombre)
            df = pd.read_sql_query(query, conn)

            fig, ax = plt.subplots(figsize = (16,9))        
            ax.plot(df['time'], df['value'])
            ax.get_xaxis().set_visible(False)

            output = io.BytesIO()
            FigureCanvas(fig).print_png(output)
            encoded_img = base64.encodebytes(output.getvalue())

            return Response(encoded_img, mimetype='image/png')
        except:
            print(traceback.format_exc())
            return jsonify({'trace': traceback.format_exc()})


@app.route('/monitor/tabla')
def tabla():
    try:
        # Enviar los datos para completar tabla
        df = pd.read_csv("tabla.csv")
        result = df.to_json()
        return(result)
    except:
        return jsonify({'trace': traceback.format_exc()})


@app.route('/monitor/reporte')
def reporte():
    try:
        # Genero el reporte del usuario solicitado
        fig, ax = plt.subplots(figsize = (16,9))        
        img=mpimg.imread('deteccion_estres.png')
        ax.imshow(img)
        ax.set_title('Detector de estrés con inteligencia artificial')
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
       
        output = io.BytesIO()
        FigureCanvas(fig).print_png(output)
        return Response(output.getvalue(), mimetype='image/png')
    except:
        return jsonify({'trace': traceback.format_exc()})


if __name__ == '__main__':
    try:
        port = int(sys.argv[1]) # This is for a command-line argument
    except:
        port = 5000 # Puerto default
        
    app.run(host='0.0.0.0', port=port, debug=True)
