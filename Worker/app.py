from datetime import datetime
import random
import json
import math
from flask import Flask, request

global currentTicketId
currentTicketId = random.randint(100000, 999999)

global parkingsData
parkingsData = {}

app = Flask(__name__)


@app.route("/entry", methods=['POST'])
def entry():
    global currentTicketId
    global parkingsData

    ticketId = currentTicketId
    currentTicketId += 1
    parkingData = ParkingData(
        request.args['plate'], request.args['parkingLot'], datetime.now(), ticketId)

    parkingsData[str(parkingData.ticketId)] = parkingData

    return json.dumps(parkingData.ticketId)


@app.route("/exit", methods=['POST'])
def exit():
    global parkingsData

    ticketId = request.args['ticketId']
    parkingData = parkingsData[ticketId]

    totalParkTime = datetime.now()-parkingData.parkingTime
    totalParkTimeIn15Minutes = math.floor(totalParkTime.total_seconds() / 60 / 15)
    charge = 2.5 * totalParkTimeIn15Minutes

    exitData = {
        'licensePlate': parkingData.plate,
        'totalParkedTime': totalParkTime,
        'parkingLotId': parkingData.parkingLot,
        'charge': charge
    }

    return json.dumps(exitData, indent=4, sort_keys=True, default=str)


class ParkingData:
    def __init__(self, plate, parkingLot, parkingTime, ticketId):
        self.plate = plate
        self.parkingLot = parkingLot
        self.parkingTime = parkingTime
        self.ticketId = ticketId