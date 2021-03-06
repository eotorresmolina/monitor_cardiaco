#!/usr/bin/env python
'''
Monitor cardíaco
---------------------------
Autor: Inove Coding School
Version: 1.0
 
Descripcion:
Se utiliza Flask para crear un WebServer que levanta los datos de
las personas que registran su ritmo cardíaco.

Ejecución: Lanzar el programa y abrir en un navegador la siguiente dirección URL
NOTA: Si es la primera vez que se lanza este programa crear la base de datos
entrando a la siguiente URL
http://127.0.0.1:5000/monitor/reset

Ingresar a la siguiente URL
http://127.0.0.1:5000/monitor

Nos deberá aparecer el una tabla con todas las personas que registraron
su ritmo cardíaco en el sistema, de cada una podremos ver el historial
cargador.

- Podremos también generar nuevos registros en el sistema ingresando a:
http://127.0.0.1:5000/monitor/registro

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
import matplotlib
matplotlib.use('Agg')   # For multi thread, non-interactive backend (avoid run in main loop)
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt

app = Flask(__name__)
client = mqtt.Client()

@app.route("/")
def index():
    return redirect('/monitor')


@app.route("/monitor")
def monitor():
    return render_template('monitor/index.html')


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
    
    start_date_str = '2019-05-10 12:00:00.0'
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d %H:%M:%S.%f')

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


@app.route('/monitor/equipo', methods=['POST', 'GET'])
def equipo():
    if request.method == 'GET':

        if client.is_connected() is False:
            try:
                client.connect("190.195.235.124", 1883, 10)
                print("Conectado al servidor MQTT")
                client.loop_start()
            except:
                print("No pudo conectarse")

        # Si entré por "GET" es porque acabo de cargar la página
        try:
            return render_template('monitor/equipo.html')
        except:
            return jsonify({'trace': traceback.format_exc()})

    if request.method == 'POST':
        # Si entré por "POST" es porque se ha precionado el botón "Enviar"
        try:
            # Solicito que me sigan reportando los valores HR por MQTT
            client.publish("/config/flag_HR_web",'1')
            nombre = str(request.form.get('name'))

            if(nombre is None):
                # Datos ingresados incorrectos
                return Response(status=404)

            # Busco todos los registros de ritmo cardíaco realizados a nombre
            # del equipo
            conn = sqlite3.connect('heartcare.db')
            c = conn.cursor()
            c.execute('select * FROM (select time from heartrate WHERE name = "{}" order by time desc LIMIT 250) order by time'.format(nombre))
            query_output = c.fetchone()
            if query_output == None:
                print("Invalid query")
                return Response(status=404)
            
            time = query_output[0]

            query = 'select time,value from heartrate WHERE name = "{}" AND time >= "{}"'.format(nombre,time)
            df = pd.read_sql_query(query, conn)

            fig, ax = plt.subplots(figsize = (16,9))        
            ax.plot(df['time'], df['value'])
            ax.get_xaxis().set_visible(False)

            output = io.BytesIO()
            FigureCanvas(fig).print_png(output)
            encoded_img = base64.encodebytes(output.getvalue())
            plt.close(fig)
            return Response(encoded_img, mimetype='image/png')
        except:
            print(traceback.format_exc())
            return jsonify({'trace': traceback.format_exc()})


@app.route('/monitor/registro', methods=['POST', 'GET'])
def registro():
    if request.method == 'GET':
        # Si entré por "GET" es porque acabo de cargar la página
        try:
            return render_template('monitor/registro.html')
        except:
            return jsonify({'trace': traceback.format_exc()})

    if request.method == 'POST':
        # Si entré por "POST" es porque se ha precionado el botón "Enviar"
        try:

            nombre = str(request.form.get('name'))
            pulsos = str(request.form.get('heart_rate'))

            if(nombre is None or pulsos is None or pulsos.isdigit() is False):
                # Datos ingresados incorrectos
                return Response(status=404)

            # Ya que pandas tiene una interfaz comoda para exportar
            # un dataframe a SQL crearemos un dataframe con los datos
            # enviados desde la API
            columns = ['time', 'name', 'value']
            heartrate = pd.DataFrame(columns=columns)
            heartrate = heartrate.append({
                                        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                                        'name': nombre,
                                        'value': int(pulsos)},
                                        ignore_index=True)

            # Persisto lo datos en la base de datos
            conn = sqlite3.connect('heartcare.db')
            heartrate.to_sql('heartrate', conn, if_exists='append', index = False)

            # Busco todos los registros de ritmo cardíaco realizados a nombre
            # de la persona
            c = conn.cursor()
            c.execute('select * FROM (select time from heartrate WHERE name = "{}" order by time desc LIMIT 250) order by time'.format(nombre))
            query_output = c.fetchone()
            if query_output == None:
                print("Invalid query")
                return Response(status=404)
            
            time = query_output[0]

            query = 'select time,value from heartrate WHERE name = "{}" AND time >= "{}"'.format(nombre,time)
            #query = 'select time,value from heartrate WHERE name = "{}" LIMIT 250'.format(nombre)
            df = pd.read_sql_query(query, conn)

            if(df.shape[0] == 1):   # Hay solo un dato ingresado
                # Duplico la información
                df = df.append({
                                'time': (datetime.now() + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S.%f"),
                                'name': nombre,
                                'value': int(pulsos)},
                                ignore_index=True)

            fig, ax = plt.subplots(figsize = (16,9))        
            ax.plot(df['time'], df['value'])
            ax.get_xaxis().set_visible(False)

            output = io.BytesIO()
            FigureCanvas(fig).print_png(output)
            encoded_img = base64.encodebytes(output.getvalue())
            plt.close(fig)
            return Response(encoded_img, mimetype='image/png')
        except:
            print(traceback.format_exc())
            return jsonify({'trace': traceback.format_exc()})


@app.route('/monitor/tabla')
def tabla():
    try:
        query = 'SELECT h_order.time, h_order.name, h_order.value, COUNT(name) as count \
                FROM (SELECT time, name, value FROM heartrate ORDER BY time) as h_order \
                GROUP BY name ORDER BY time;'

        conn = sqlite3.connect('heartcare.db')
        df = pd.read_sql_query(query, conn)

        # Enviar los datos para completar tabla
        result = df.to_json()
        return(result)
    except:
        return jsonify({'trace': traceback.format_exc()})


@app.route('/monitor/tabla/historico')
def historico():
    try:
        nombre = request.args.get('name')

        if nombre is None:
            # No se ha enviado ningún nombre para mostrar
            # el histórico, regreso a la tabla
            return redirect('/monitor')
        
        # Busco todos los registros de ritmo cardíaco realizados a nombre
        # de la persona
        conn = sqlite3.connect('heartcare.db')
        c = conn.cursor()
        c.execute('select * FROM (select time from heartrate WHERE name = "{}" order by time desc LIMIT 250) order by time'.format(nombre))
        query_output = c.fetchone()
        if query_output == None:
            print("Invalid query")
            return Response(status=404)
        
        time = query_output[0]

        query = 'select time,value from heartrate WHERE name = "{}" AND time >= "{}"'.format(nombre,time)
        #query = 'select time,value from heartrate WHERE name = "{}" LIMIT 250'.format(nombre)
        df = pd.read_sql_query(query, conn)

        if(df.shape[0] == 0):   # No hay datos ingresados
            return redirect('/monitor')

        if(df.shape[0] == 1):   # Hay solo un dato ingresado
            # Duplico la información
            first_date = datetime.strptime(df.loc[0,'time'], '%Y-%m-%d %H:%M:%S.%f')
            pulsos = df.loc[0,'value']
            df = df.append({
                        'time': (first_date + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S.%f"),
                        'name': nombre,
                        'value': int(pulsos)},
                        ignore_index=True)

        # Genero el reporte del usuario solicitado
        fig, ax = plt.subplots(figsize = (16,9))        
        ax.plot(df['time'], df['value'])
        ax.get_xaxis().set_visible(False)

        output = io.BytesIO()
        FigureCanvas(fig).print_png(output)
        plt.close(fig)
        return Response(output.getvalue(), mimetype='image/png')
    except:
        return jsonify({'trace': traceback.format_exc()})


def on_connect(client, userdata, flags, rc):
    print("MQTT Conectado - Codigo de resultado: "+str(rc))
    client.subscribe("/movil/HR")

# Callback cuando se recibe un publish del topico suscripto
def on_message(client, userdata, msg):
    mensaje = str(msg.payload.decode("utf-8"))
    # lista = msg.topic.split("/")
    # print(msg.topic,'msg:',mensaje)

    pulsos = mensaje
    columns = ['time', 'name', 'value']
    heartrate = pd.DataFrame(columns=columns)
    heartrate = heartrate.append({
                                'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                                'name': 'equipo1',
                                'value': int(pulsos)},
                                ignore_index=True)

    # Persisto lo datos en la base de datos
    conn = sqlite3.connect('heartcare.db')
    heartrate.to_sql('heartrate', conn, if_exists='append', index = False)
    #print(msg.topic+" "+str(msg.payload))

def on_publish(client,userdata,result):             #create function for callback
    #print("data published \n")
    pass

client.on_connect = on_connect
client.on_message = on_message
client.on_publish = on_publish

if __name__ == '__main__':
    print('Inove@Monitor Cardíaco start!')    
    try:
        port = int(sys.argv[1])
    except:
        port = 5000 # Puerto default
        
    app.run(host='0.0.0.0', port=port, debug=True)
