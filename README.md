# twc3-modbus
script to give modbus responses to a tesla wall connector v3
it matches a request recieved on serial port , to defined responses, which it then uses in the response.

the responses are in the responses location, and the file name is matched to the request, and the contents used in the response.

using information from https://github.com/dracoventions/TWCManager/issues/20

normal mode
python -u tesla.py

Specify Custom Port:
python -u tesla.py --port /dev/ttyUSB1

Dummy Mode (Simulation):
python -u tesla.py --dummy
