from ftplib import FTP
import ntpath
import os
from os import listdir
from os.path import isfile, join
import RPi.GPIO as GPIO
import xml.etree.ElementTree as ET
from datetime import datetime
import time
import logging

TERMINAL_IP = 'localhost'
TERMINAL_USER =  'pi'
TERMINAL_PASSWORD = 'teamd#1!'

files_from_terminal_in_host = '/home/host/files_from_terminal'

#FUTURE_PASS_TIME_FORMAT = "#DD-MM-YYY:MM:SS,DD-MM-YYY:MM:SS#<cr><lf>"
FUTURE_PASS_TIME_FORMAT = "%d-%m-%Y %H:%M:%S"
FUTURE_PASSES_FILE = '/home/terminal/data/config/future_pass.txt'
PASS_START_TAG = "start_pass_time"
PASS_END_TAG = "stop_pass_time"
MEMORY_TAG = "memory_left"

class FTPClass(object):
	"""docstring for FTP"""
	def __init__(self, ip, user, password):
		self.ip = ip
		self.user = user
		self.password = password
		self.is_close = True
		self.logger = logging.getLogger(__name__)

	def connect(self):
		self.is_close = False
		return FTP(self.ip, self.user, self.password)

	def get_all_files_from_terminal(self, connection):
		'''
		Going through all the data directories in the Terminal,
		and send them to the Host.
		After a file sent succesfully it will be deleted from the Terminal.
		'''
		host_path = '/home/terminal/data/'
		print(connection)
		terminal_dir_list = connection.nlst('/home/terminal/data/')
		for dir in terminal_dir_list:
			file_list = connection.nlst(dir)
			for full_file_name in file_list:
				handle = open(full_file_name, 'wb')
				if self.completed_succesfully(connection.retrbinary('RETR %s' % full_file_name, handle.write)):
					self.logger.info("Got file " + full_file_name + " succesfully")
					if self.completed_succesfully(connection.delete(full_file_name)):
						self.logger.info("File " + full_file_name + " deleted succesfully")
					else:
						self.logger.warning("Could not delete " + full_file_name)
				else:
					self.logger.warning("Could not get " + full_file_name)

	def send_all_files_to_terminal(self, connection):
		'''
		Going through all the directories in the Host by the prioritization order,
		and send them to the Terminal.
		After a file sent succesfully, it is sent again with a .done extension.
		'''
		host_path = '/home/terminal/payload/to_gw/'
		host_dir_list = [x[0] for x in os.walk(host_path)]
		host_dir_list = host_dir_list[1:]
		sorted_host_dir_list = sorted(host_dir_list, key = lambda dir: dir[-2:] if (dir[-2:].isdigit()) else (dir[-1:]))
		for dir in sorted_host_dir_list:
			file_list = listdir(dir)
			'''file_list = [f for f in listdir(mypath) if isfile(join(mypath, f))]'''
			for filename in file_list:
				''' opened file is the file to transfer from host'''
				file_name = join(host_path,dir,filename)
				file_from_host = open(filename,'rb')
				file_name_in_terminal = file_from_host
				if self.completed_succesfully(connection.storbinary('STOR %s' % file_name_in_terminal, file_from_host)):
					self.logger.info("Send file " + full_file_name + " succesfully") 
					done_file = file_name_in_terminal + ".done"
					if self.completed_succesfully(connection.storbinary('STOR %s' % done_file, file_from_host)):
						self.logger.info("Send file " + done_file + " succesfully")
					else:
						self.logger.warning("Could not send " + done_file)
				else:
					self.logger.warning("Could not send " + full_file_name)

	def close(self, connection):
		connection.close()
		self.logger.info("closing ftp connection")

	def completed_succesfully(self, telemetry):
		self.logger.info(telemetry)
		return "226" in telemetry


class DigitalOn(object):
	"""docstring for DigitalOn"""
	def __init__(self):
		self.pin = 28
		self.isOn = False
		self.logger = logging.getLogger(__name__)
		GPIO.setmode(GPIO.BCM)
		GPIO.setwarnings(False)
		GPIO.setup(self.pin, GPIO.OUT)

	def send_digital_on(self):
		''' 3.3 V'''
		GPIO.output(self.pin, GPIO.HIGH)
		self.isOn = True
		self.logger.info("sent digital on")

	def send_digital_off(self):
		''' 0 V'''
		GPIO.output(self.pin, GPIO.LOW)
		self.isOn = False
		self.logger.info("sent digital off")



def read_conf_file():
	pass_start_to_end_time_dict = {}
	with open (FUTURE_PASSES_FILE, 'r') as file:
		data = file.readlines()
	for line in data:
		values = line[1:-1].split(",")
		pass_start_time_string = values[0] + " " + values[1]
		pass_end_time_string = values[2] + " " + values[3]
		pass_start_time_datetime = datetime.strptime(pass_start_time_string , FUTURE_PASS_TIME_FORMAT)
		pass_end_time = datetime.strptime(pass_end_time_string , FUTURE_PASS_TIME_FORMAT)
		pass_start_to_end_time_dict[pass_start_time] = pass_end_time
	return pass_start_to_end_time_dict



def main():
	'''
	Read the configurtion file.
	If its pass time, send Digital off and sleep.
	If not, open FTP session and (if not open)
	Get all files from terminal, and Send all files to terminal
	'''
	logging.basicConfig(level=logging.INFO)
	logger = logging.getLogger(__name__)
	handler = logging.FileHandler('/home/terminal/host_log.log')
	handler.setLevel(logging.INFO)

	# create a logging format
	formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
	handler.setFormatter(formatter)

	# add the file handler to the logger
	logger.addHandler(handler)

	ftp = FTPClass(TERMINAL_IP, TERMINAL_USER, TERMINAL_PASSWORD)
	digitalOn = DigitalOn()
	while True:
		pass_start_to_end_time_dict = read_conf_file()
		for pass_start_time in pass_start_to_end_time_dict:
			pass_end_time = pass_start_to_end_time_dict[pass_start_time]
			if pass_start_time <= datetime.now() <= pass_end_time:
				logger.info("pass time, closing connection and going to sleep")
				if not ftp.is_close:
					FTP.close(connection)
				digitalOn.send_digital_off()
				time.sleep((pass_end_time - datetime.now()).total_seconds())
				continue

		if not digitalOn.isOn:
			digitalOn.send_digital_on()
		if ftp.close:
			connection = ftp.connect()
		ftp.get_all_files_from_terminal(connection)
		ftp.send_all_files_to_terminal(connection)


if __name__ == '__main__':
	main()