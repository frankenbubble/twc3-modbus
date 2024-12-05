# v0.1
import os
import sys
import logging
import argparse
from pymodbus.server.sync import StartSerialServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.transaction import ModbusRtuFramer
import serial
import time

# Configure logging to ensure output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('modbus_server.log', mode='w'),  # Overwrite mode
        logging.StreamHandler(sys.stdout)  # Explicitly use stdout
    ]
)
logger = logging.getLogger(__name__)
logger.propagate = True  # Ensure log messages are propagated

class FileBasedModbusDataStore(ModbusSlaveContext):
    def __init__(self, response_dir='responses', dummy_mode=False):
        """
        Initialize the datastore with a directory of response files
        
        :param response_dir: Directory containing response files
        :param dummy_mode: Whether to run in dummy (simulation) mode
        """
        super().__init__()
        self.response_dir = response_dir
        self.dummy_mode = dummy_mode
        logger.info(f"Initialized DataStore. Dummy Mode: {dummy_mode}")
    
    def format_modbus_response(self, slave_address, function_code, values):
        """
        Construct a full Modbus RTU response frame
        
        :param slave_address: Slave address
        :param function_code: Modbus function code
        :param values: List of register values
        :return: Hex representation of full Modbus RTU response
        """
        # Byte count is number of registers * 2 (16-bit per register)
        byte_count = len(values) * 2
        
        # Construct response payload
        payload = [
            slave_address,  # Slave address
            function_code,  # Function code
            byte_count      # Byte count
        ]
        
        # Add register values (16-bit big-endian)
        for value in values:
            payload.extend([(value >> 8) & 0xFF, value & 0xFF])
        
        # Calculate CRC
        crc = self.calculate_crc(payload)
        payload.extend([crc & 0xFF, (crc >> 8) & 0xFF])
        
        # Convert to hex string
        return ' '.join(f'{x:02X}' for x in payload)
    
    def calculate_crc(self, data):
        """
        Calculate Modbus RTU CRC
        
        :param data: List of bytes
        :return: 16-bit CRC
        """
        crc = 0xFFFF
        for x in data:
            crc ^= x
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    def validate_file_response(self, register_address, count):
        """
        Read response from file based on register address and count
        
        :param register_address: Modbus register address 
        :param count: Number of registers to read
        :return: List of register values or None
        """
        # Construct file path (e.g., responses/40002)
        file_path = os.path.join(self.response_dir, str(register_address))
        
        try:
            with open(file_path, 'r') as f:
                # Read hex values, stripping whitespace and '0x'
                hex_values = [
                    int(line.strip(), 16) 
                    for line in f 
                    if line.strip().startswith('0x')
                ]
                
                # Check if we have enough data
                if len(hex_values) < count:
                    logger.warning(f"Insufficient data for register {register_address}. "
                                   f"Requested {count}, but only {len(hex_values)} available.")
                    return None
                
                # Log details about the file and request
                logger.info(f"Request for register {register_address}: "
                            f"Requested {count} registers, "
                            f"File contains {len(hex_values)} values")
                
                # Return only the requested number of registers
                return hex_values[:count]
        
        except FileNotFoundError:
            logger.warning(f"No response file found for register {register_address}")
            return None
        except ValueError as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            return None
    
    def getValues(self, fx, address, count=1):
        """
        Override getValues to provide file-based responses with logging
        
        :param fx: Modbus function code
        :param address: Starting register address
        :param count: Number of registers to read
        :return: List of register values
        """
        # Log the incoming request details
        logger.info(f"Received request: "
                    f"Function Code: {fx}, "
                    f"Address: {address}, "
                    f"Count: {count}")
        
        if fx in [3, 4]:  # Read Holding Registers or Input Registers
            values = self.validate_file_response(address, count)
            
            # Only return values if a valid response was found
            if values is not None:
                # Format and log full Modbus response
                full_response = self.format_modbus_response(
                    slave_address=1,  # Default slave address
                    function_code=fx,
                    values=values
                )
                
                # In dummy mode, just log. In normal mode, return values
                if not self.dummy_mode:
                    logger.info(f"Full Modbus Response (Hex): {full_response}")
                    return values
                else:
                    logger.info(f"Full Modbus Response (not sent) (Hex): {full_response}")
            
            # Return None if no valid response (effectively no response)
            return None
        
        # Default behavior for other function codes
        return super().getValues(fx, address, count)

def run_modbus_server(port='/dev/ttyUSB0', baudrate=115200, dummy_mode=False):
    """
    Run Modbus RTU server over RS485
    
    :param port: Serial port
    :param baudrate: Communication speed
    :param dummy_mode: Whether to run in dummy (simulation) mode
    """
    # Create a datastore
    datastore = FileBasedModbusDataStore(dummy_mode=dummy_mode)
    context = ModbusServerContext(slaves={1: datastore}, single=False)
    
    # Device identification
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'Modbus Server'
    identity.ProductCode = 'MS001'
    identity.VendorUrl = 'http://example.com'
    
    try:
        # Start the server
        logger.info(f"Starting Modbus RTU Server on {port} at {baudrate} baud")
        logger.info(f"Dummy Mode: {'Enabled' if dummy_mode else 'Disabled'}")
        # List all available response files
        response_files = os.listdir('responses')
        logger.info(f"Available response files: {response_files}")
        
        if dummy_mode:
            # In dummy mode, simulate server behavior
            logger.info("Dummy Mode: Simulating Modbus server responses")   
        
        # Normal server mode
        StartSerialServer(
            context, 
            framer=ModbusRtuFramer,
            identity=identity,
            port=port, 
            timeout=1,
            baudrate=baudrate
        )
    except serial.SerialException as e:
        logger.error(f"Serial port error: {e}")
    except Exception as e:
        logger.error(f"Server error: {e}")

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Modbus RTU Server')
    parser.add_argument('--dummy', action='store_true', 
                        help='Run in dummy mode (simulation only)')
    parser.add_argument('--port', default='/dev/ttyUSB0', 
                        help='Serial port to use')
    parser.add_argument('--baudrate', type=int, default=115200, 
                        help='Baudrate for serial communication')
    
    args = parser.parse_args()
    
    # Ensure response directory exists
    os.makedirs('responses', exist_ok=True)
    
    # Run the server
    run_modbus_server(
        port=args.port, 
        baudrate=args.baudrate, 
        dummy_mode=args.dummy
    )

if __name__ == '__main__':
    main()
