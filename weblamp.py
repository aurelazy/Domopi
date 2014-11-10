#!/usr/bin/env python
# -*- coding:utf-8 -*-

import time
from Adafruit_I2C import Adafruit_I2C
from flask import Flask, render_template, request, session, g, redirect, url_for, abort, flash
from flask.ext.bootstrap import Bootstrap
from flask.ext.moment import Moment
import struct
from datetime import datetime
import os
import re
import sys
import ConfigParser
import pywapi


reload(sys)
sys.setdefaultencoding("utf-8")

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
bootstrap = Bootstrap(app)
moment = Moment(app)
config = ConfigParser.RawConfigParser()

i2c = Adafruit_I2C(0x04)
fichier = '/home/pi/Flask/tmp/etat_'

app.secret_key = "m@_Sup3r_c73_s3cr3t3"

def getWeather():
	result = pywapi.get_weather_from_yahoo('FRXX1567', 'metric')
	string = result['html_description']
	string = string.replace("\n", "")
	# On enleve le surplus et la pub ;-)
	string = string.replace("(provided by <a href=\"http://www.weather.com\" >The Weather Channel</a>)<br/>", "")
	string = string.replace("<br /><a href=\"http://us.rd.yahoo.com/dailynews/rss/weather/Cachan__FR/*http://weather.yahoo.com/forecast/FRXX1567_c.html\">Full Forecast at Yahoo! Weather</a><BR/><BR/>", "")
    
	return string

def readTemp():
	i2c.write8(0,0x04)
	time.sleep(0.100)
	lstData = i2c.readList(0x00, 4)
	sData = ""
	for aByte in lstData:
		sData = sData + chr(aByte)

	f_data = struct.unpack('<f', sData)
	temp = []
	for f in f_data:
		temp.append(f)

	temp = float(temp[0])
	temp = round(temp, 1)

	return temp

def readLum():
	i2c.write8(0x00,0x05)
	time.sleep(0.100)
	i2c.readU8(0x00)

def readled(led):
	i2c.write8(0x00,led)
	etat = i2c.readU8(0x00)
	return etat

def readled_file(led):
	try:
		f = open(fichier+led, 'r')
		etat = int(f.read())
		f.close()
	except IOError:
		etat = 0
	return etat

lumieres = {
	6 : {'name' : 'ampli', 'etat' : 0, 'registre' : 2},
	7 : {'name' : 'fleurs', 'etat' : 0, 'registre' : 3},
	8 : {'name' : 'Milla', 'etat' : 0, 'registre' : 4},
	9 : {'name' : 'Charlie', 'etat' : 0, 'registre' : 5}
	}

thermo = {
	'com' : 3,
	'etat' : 0,
	'registre' : 1
	}

@app.route("/")
def main():
	temp = readTemp()
	
	for lum in lumieres:
		lumieres[lum]['etat'] =  readled_file(lumieres[lum]['name'])

	templateData = {
		'title' : 'Maison',
	#	'Temp' : temp,
		'lumieres' : lumieres,
	}
	return render_template('light.html', **templateData)

@app.route("/<lieu>/<action>")
def action(lieu, action):
	deviceName = lieu
	temp = readTemp()
	
	for lum in lumieres:
		if lumieres[lum]['name'] == deviceName:
			changePin = int(lum)
			registre = lumieres[lum]['registre']

	if action == "on":
		i2c.write8(registre, 1)
		time.sleep(0.020)
		i2c.write8(0x00, changePin)
		time.sleep(0.100)
		f = open(fichier+lieu, 'w')
		f.write("1")
		f.close()
		if lieu == 'Charlie' or lieu == 'Milla':
			flash("On allume la lumiere de " + lieu)
		elif lieu == 'ampli':
			flash("On allume l'" + lieu)
		else:
			flash("On allume la lumiere de la " + lieu)

	if action == "off":	
		i2c.write8(registre, 0)
		time.sleep(0.020)
		i2c.write8(0x00, changePin)
		time.sleep(0.100)
		f = open(fichier+lieu, 'w')
		f.write("0")
		f.close()
		if lieu == 'Charlie' or lieu == 'Milla':
			flash("On eteint la lumiere de " + lieu)
		elif lieu == 'ampli':
			flash("On eteint l'" + lieu)
		else:
			flash("On eteint la lumiere de la " + lieu)
	
	for lum in lumieres:
		lumieres[lum]['etat'] =  readled_file(lumieres[lum]['name'])

	templateData = {
		'lumieres' : lumieres,
		'Temp' : temp,
	}

	return render_template('light.html', **templateData)	
	
@app.route('/_liveTemp', methods= ['GET'])
def updateTemp():
	return str(readTemp())

@app.route('/_liveDate', methods= ['GET'])
def updateDate():
	temp = readTemp()

	f = open('status', 'r')
	targetTemp = f.readline().strip()
	mode = f.readline()
	f.close()

	config.read('config.cfg')
	onMatin = config.get('horaires', 'onMatin')
	offMatin = config.get('horaires', 'offMatin')
	onSoir = config.get('horaires', 'onSoir')
	offSoir = config.get('horaires', 'offSoir')

# OK ca fonctionne
	# On allume la chaudiere le matin
	if mode == 'auto':
		if onMatin <= datetime.now().strftime("%H:%M") < offMatin and temp < int(targetTemp):
			i2c.write8(thermo['registre'], 1)
			time.sleep(0.020)
			i2c.write8(0x00, thermo['com'])
			time.sleep(0.100)
			f = open(fichier + 'thermostat', 'w')
			f.write("1")
			f.close()

		elif datetime.now().strftime("%H:%M") == offMatin:
			for lum in lumieres:
				i2c.write8(int(lumieres[lum]['registre']), 0)
				time.sleep(0.100)
				i2c.write8(0x00, int(lum))
				time.sleep(0.100)
				f = open(fichier + lumieres[lum]['name'], 'w')
				f.write("0")
				f.close()

		# On eteint la chaudiere le matin:
		elif offMatin <= datetime.now().strftime("%H:%M") < onSoir:
			i2c.write8(thermo['registre'], 0)
			time.sleep(0.020)
			i2c.write8(0x00, thermo['com'])
			f = open(fichier + 'thermostat', 'w')
			f.write('0')
			f.close()

		# On allume la chaudiere le soir:
		elif onSoir <= datetime.now().strftime("%H:%M") < offSoir and temp <= int(targetTemp):
			i2c.write8(thermo['registre'], 1)
			time.sleep(0.020)
			i2c.write8(0x00, thermo['com'])
			time.sleep(0.100)
			f = open(fichier + 'thermostat', 'w')
			f.write('1')
			f.close()

		# On eteint la chaudiere le soir:
		elif offSoir <= datetime.now().strftime("%H:%M") <= '23:59' or '00:00' <= datetime.now().strftime("%H:%M") < onMatin:
			i2c.write8(thermo['registre'], 0)
			time.sleep(0.020)
			i2c.write8(0x00, thermo['com'])
			time.sleep(0.100)
			f = open(fichier + 'thermostat', 'w')
			f.write('0')
			f.close() 
			
		else:
			i2c.write8(thermo['registre'], 0)
			time.sleep(0.020)
			i2c.write8(0x00, thermo['com'])
			time.sleep(0.100)
			f = open(fichier + 'thermostat', 'w')
			f.write('0')
			f.close() 
			
	else:
		if datetime.now().strftime("%H:%M") == offMatin:
		# On eteint toutes les lumieres le matin:
			for lum in lumieres:
				i2c.write8(lumieres[lum]['registre'], 0)
				time.sleep(0.100)
				i2c.write8(0x00, int(lum))
				time.sleep(0.100)
				f = open(fichier + lumieres[lum]['name'], 'w')
				f.write("0")
				f.close()
			
	return datetime.now().strftime("%A %d %B %Y, %H:%M")	

@app.route('/thermostat')
def thermostat():
	f = open("status", 'r')
	targetTemp = f.readline().strip()
	mode = f.readline()
	f.close()

	thermo['etat'] = readled_file('thermostat')	

	templateData = {
		'targetTemp' : targetTemp,
		'thermo' : thermo,
		'mode' : mode,
	}

	return render_template('thermostat.html', **templateData)

@app.route('/thermostat', methods=['POST'])
def thermostat_post():
	text = request.form['target']

	f = open('status', 'r')
	targetTemp = f.readline().strip()
	mode = f.readline()
	f.close()

	newTargetTemp = text.upper()
	match = re.search(r'^\d{2}$', newTargetTemp)
	if match:
		f = open('status', 'w')
		f.write(newTargetTemp + '\n' + mode)
		f.close()
		flash("Nouvelle temperature de " + newTargetTemp + "° enregistree!")

		return redirect(url_for('thermostat'))
	else:
		flash("ERREUR, Entrez un nombre a 2 chiffres SVP!")
		
		return redirect(url_for('thermostat'))

@app.route('/thermostat/manuel/<action>')
def action_manuel_thermo(action):
	f = open("status", 'r')
	targetTemp = f.readline().strip()
	mode = f.readline()
	f.close()

	lieu = 'thermostat'
	changePin = int(thermo['com'])
	registre = thermo['registre']

	if action == "on":
		i2c.write8(registre, 1)
		time.sleep(0.020)
		i2c.write8(0x00, changePin)
		time.sleep(0.100)
		f = open(fichier+lieu, 'w')
		f.write("1")
		f.close()
		flash("OK, le thermostat est allume.")

	if action == "off":	
		i2c.write8(registre, 0)
		time.sleep(0.020)
		i2c.write8(0x00, changePin)
		time.sleep(0.100)
		f = open(fichier+lieu, 'w')
		f.write("0")
		f.close()
		flash("OK, le thermostat est eteint.")
	
	thermo['etat'] =  readled_file('thermostat')

	templateData = {
		'thermo' : thermo,
		'targetTemp' : targetTemp,
		'mode' : mode,
	}

	return render_template('thermostat.html', **templateData)	

@app.route('/thermostat/<newMode>')
def action_auto_thermo(newMode):
	f = open('status', 'r')
	targetTemp = f.readline().strip()
	mode = f.readline()
	f.close()

	if newMode == 'auto':
		mode = newMode
		f = open('status', 'w')
		f.write(targetTemp + "\n" + mode)
		f.close()
		flash("OK, le mode thermostat est en automatique.")

	if newMode == 'manuel':
		mode = newMode
		f = open('status', 'w')
		f.write(targetTemp + "\n" + mode)
		f.close()
		flash("OK, le mode thermostat est en manuel.")

	if newMode == 'freeze':
		mode = newMode
		f = open('status', 'w')
		f.write(targetTemp + "\n" + mode)
		f.close()
		flash("OK, le mode thermostat est en Hors-Gel.")

	thermo['etat'] = readled_file('thermostat')

	templateData = {
		'thermo' : thermo,
		'targetTemp' : targetTemp,
		'mode' : mode,
	}
	
	return render_template('thermostat.html', **templateData)

@app.route('/configuration')
def configuration():
	config.read('config.cfg')
	onMatin = config.get('horaires', 'onMatin')
	offMatin = config.get('horaires', 'offMatin')
	onSoir = config.get('horaires', 'onSoir')
	offSoir = config.get('horaires', 'offSoir')

	templateData = {
		'onMatin' : onMatin,
		'offMatin' : offMatin,
		'onSoir' : onSoir,
		'offSoir' : offSoir,
	}

	return render_template('configuration.html', **templateData)

@app.route('/configuration', methods=['POST'])
def configuration_post():
	newOnMatin = request.form['onMatin']
	newOffMatin = request.form['offMatin']
	newOnSoir = request.form['onSoir']
	newOffSoir = request.form['offSoir']

	list_h = [['onMatin', newOnMatin], ['offMatin', newOffMatin], ['onSoir', newOnSoir], ['offSoir', newOffSoir]]
	for h in list_h:
		match = re.search(r'^\d{2}:\d{2}$', h[1])
		if match:
			config.set('horaires', h[0], h[1])
			with open('config.cfg', 'w') as configfile:
				config.write(configfile)
			flash("Nouvel horaire enregistre." + h[0])
		else:
			flash("ERREUR sur " + h[0] + ", l'heure doit etre sous cette forme: 00:00")

	return redirect(url_for('configuration'))

@app.route('/weather')
def weather():
	weatherString = getWeather()

	templateData = {
		'weatherString' : weatherString,
	}
	
	return render_template("meteo.html", **templateData)

@app.errorhandler(404)
def page_not_found(e):
	return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
	return render_template('500.html'), 500


if __name__ == "__main__":
	app.run(host='0.0.0.0', port=8080, debug=True)

