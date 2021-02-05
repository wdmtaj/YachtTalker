# test on Jan 06 - 0932

import os
import can
import sys
import json
from time import *
from tkinter import *
import threading
import pyttsx3
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

# Custom MQTT message callback
def customCallback(client, userdata, message):
    print(f"Received a new message: {message.payload}")
    print("from topic: ")
    print(message.topic)
    if 'exit' in str(message.payload):
        print('exit program')

# Initialize variables with AWS credentials
host = "a39fvf5mz5tuzf-ats.iot.us-east-1.amazonaws.com"     # this is the endpoint from AWS IoT Settings screen
rootCAPath = "X509_Root.crt"                                # Created from AWS IoT Certificate Creation with Policy
certificatePath = "209c3a4c4a-certificate.pem.crt"          # Created from AWS IoT Certificate Creation with Policy
privateKeyPath = "209c3a4c4a-private.pem.key"               # Created from AWS IoT Certificate Creation with Policy
                                                            # Pilocy attached to above certificate allows all
                                                            #   IoT actions and resources
                                                            # {
                                                            #   "Version": "2012-10-17",
                                                            #   "Statement": [
                                                            #     {
                                                            #       "Effect": "Allow",
                                                            #       "Action": "iot:*",
                                                            #       "Resource": "*"
                                                            #     }
                                                            #   ]
                                                            # }
port = 8883                                                 # port for secure MQTT
useWebsocket = False                                        # Not using websocket - not being used here either
clientId = "OA7821RPi4"                                     # Made up name to identify this client
topic = "OA7821_Update"                     # MQTT Topic
message = 'Hello from OA7821'


# Init AWSIoTMQTTClient
myAWSIoTMQTTClient = None
myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
myAWSIoTMQTTClient.configureEndpoint(host, port)
myAWSIoTMQTTClient.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

# AWSIoTMQTTClient connection configuration
myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureOfflinePublishQueueing(0)  # Infinite offline Publish queueing is -1
myAWSIoTMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec

# Connect and subscribe to AWS IoT
myAWSIoTMQTTClient.connect()
myAWSIoTMQTTClient.subscribe('data_from_OA7821', 1, customCallback)
sleep(2)

false = False

# Alexa JSON data structure with additions for CAN bus data at end
alexa_message = {
    "version": "1.0",
    "session": {
        "new": false,
        "sessionId": "OA7821",
        "application": {
            "applicationId": ""
        },
        "user": {
            "userId": ""
        }
    },
    "context": {
        "Extensions": {
            "available": {}
        },
        "System": {
            "application": {
                "applicationId": ""
            },
            "user": {
                "userId": ""
            },
            "device": {
                "deviceId": "",
                "supportedInterfaces": {}
            },
            "apiEndpoint": "",
            "apiAccessToken": "",
            "unit": {
                "unitId": ""
            }
        }
    },
    "request": {
        "type": "OA7821_Data_Update",
        "requestId": "",
        "timestamp": "",
        "locale": "",
        "shouldLinkResultBeReturned": false
    },
    "can_bus_data": {
        "fresh_water_level": "0",
        "heading_magnetic": "",
        "black_water_level": "",
        "lattitude": "",
        "longitude": "",
        "fuel_tank_level": ""
    }
}

shadow_update_msg = {
  "desired": {
    "welcome": "OA7821 Shadow Update"
  },
  "reported": {
    "welcome": "OA7821 Shadow Update"
  },
    "can_bus_data": {
        "fresh_water_level": "0",
        "heading_magnetic": "",
        "black_water_level": "",
        "lattitude": "",
        "longitude": "",
        "fuel_tank_level": ""
    },
}

#  Start CAN Bus interface and configure
os.system('sudo ifconfig can0 down')
os.system('sudo ip link set can0 up type can bitrate 250000')
os.system('sudo ifconfig can0 up')
can0 = can.interface.Bus(channel='can0', bustype='socketcan_ctypes')

def get_can_data():  # function runs in background, reads and converts CAN bus data

    fresh_water_level = 0
    fuel_tank_level = 0
    black_water_level = 0
    lattitude = 0
    longitude = 0
    heading_magnetic = 0

    while True:
        try:
            can_packet = str(can0.recv(5))
        except:
            print(f'CAN Bus error')
        if "None" in can_packet:
            print(f'No data read from CAN bus')
        if "9f112" in can_packet:                      # 9f112 is heading data
            radian_raw_string = (can_packet[can_packet.find("DLC") + 14:can_packet.find("DLC") + 19])
            reversed_radian_string = radian_raw_string.replace(" ", "")
            radian_string = reversed_radian_string[2] + reversed_radian_string[3] + reversed_radian_string[0] + \
                            reversed_radian_string[1]
            heading_radian = int(radian_string, 16) / 10000
            heading_degrees = round(heading_radian * 180 / 3.1415927, 2)
            if abs(heading_magnetic - heading_degrees) > 2:
                heading_magnetic = heading_degrees
                alexa_message['can_bus_data']['heading_magnetic'] = str(heading_degrees)
                messageJson = json.dumps(alexa_message)
                shadow_update_msg['can_bus_data']['heading_magnetic'] = str(heading_degrees)
                shadow_msg_Json = json.dumps(shadow_update_msg)
                myAWSIoTMQTTClient.publish(topic, messageJson, 1)
                myAWSIoTMQTTClient.publish("$aws/things/OA7821_PI4_Shadow/shadow/update", shadow_msg_Json, 1)

                print('Published topic %s: %s\n' % (topic, json.dumps(alexa_message)))
                print(f'Heading is {str(heading_degrees)} magnetic  ')

        if "9f211" in can_packet:                      # 9f211 are all tank level packets
            # level_raw_string = (str_msg[str_msg.find("DLC") + 14:str_msg.find("DLC") + 19])
            tank_level_string = ('Raw string: ' + can_packet[32:44] + '  ' + can_packet[
                                                                     can_packet.find("DLC") + 11:can_packet.find("DLC") + 34])
            if '9f21158  14' in tank_level_string:      # 9f211   14 is fresh water, it was 11 on prior TLM100 - not sure why it changes
                offset = tank_level_string.find(' 14')
                percent = int(tank_level_string[offset + 7:offset + 9] + tank_level_string[offset + 4:offset + 6], 16) / 25000
                tank_level = int(360 * percent)     # max tank volume is 360
                if abs(fresh_water_level-tank_level) > 4:
                    fresh_water_level = tank_level
                    alexa_message['can_bus_data']['fresh_water_level'] = str(tank_level)
                    messageJson = json.dumps(alexa_message)
                    myAWSIoTMQTTClient.publish(topic, messageJson, 1)
                    print('Published topic %s: %s\n' % (topic, json.dumps(alexa_message)))
                    print(f'Fresh water tank level is {tank_level} gallons')
            if '9f21158  52' in tank_level_string:
                offset = tank_level_string.find(' 52')
                percent = int(tank_level_string[offset + 7:offset + 9] + tank_level_string[offset + 4:offset + 6], 16) / 25000
                tank_level = int(175 * percent)     # max tank volume is 175
                if abs(black_water_level-tank_level) > 2:
                    black_water_level = tank_level
                    alexa_message['can_bus_data']['black_water_level'] = str(tank_level)
                    messageJson = json.dumps(alexa_message)
                    myAWSIoTMQTTClient.publish(topic, messageJson, 1)
                    print('Published topic %s: %s\n' % (topic, json.dumps(alexa_message)))
                    print(f'Black water tank level is {tank_level} gallons')
            if '9f21158  01' in tank_level_string:
                offset = tank_level_string.find(' 01')
                percent = int(tank_level_string[offset + 7:offset + 9] + tank_level_string[offset + 4:offset + 6], 16) / 25000
                tank_level = int(1000 * percent) * 2     # max tank volume is 1000 per side times 2 sides
                if abs(fuel_tank_level-tank_level) > 5:
                    fuel_tank_level = tank_level
                    alexa_message['can_bus_data']['fuel_tank_level'] = str(tank_level)
                    messageJson = json.dumps(alexa_message)
                    myAWSIoTMQTTClient.publish(topic, messageJson, 1)
                    print('Published topic %s: %s\n' % (topic, json.dumps(alexa_message)))
                    print(f'Fuel tank level is {tank_level} gallons')




win = Tk()  # Generate parent window for foreground GUI app
win.title("CAN - GUI Test Program")
win.geometry('700x500')

def start_bg_canbus():
    can_thread = threading.Thread(target=get_can_data, daemon=True)
    can_thread.start()


def turn_off_can_bus():
    os.system('sudo ifconfig can0 down')


def turn_on_can_bus():
    os.system('sudo ifconfig can0 up')

    # These statements build the GUI interface


l2 = Label(win, text=' ', font='Times 24 bold')
l2.pack()
b4 = Button(win, text='Start Background CAN bus reader', font='Times 24 bold', command=start_bg_canbus)
b4.pack()
b_can_off = Button(win, text='Turn CAN Bus Off', font='Times 24 bold', command=turn_off_can_bus)
b_can_off.pack()
b_can_on = Button(win, text='Turn CAN Bus On', font='Times 24 bold', command=turn_on_can_bus)
b_can_on.pack()
b_quit = Button(win, text='quit', font='Times 24 bold', command=win.quit)
b_quit.pack()

win.mainloop()  # main GUI window loop
