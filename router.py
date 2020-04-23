import configparser
import pickle
import sys
import select
import time
import threading
import socket



class RIP_demon(object):
    def __init__(self, file):
        self.file = file
        self.router_id = None
        self.ingress = []
        self.ingress_sockets = []
        self.egress = []
        self.output_lines = []
        self.config = configparser.ConfigParser()
    

    def load_startup(self):
        self.config.read(self.file)
        
        if len(self.config.get("router-id", "id")) < 1:
            print('\nInvalid router id')
            return
        if len(self.config.items("input-ports")) < 1:
            print('\nInvalid input-ports')
            return
        if len(self.config.items("output-ports")) < 1:
            print('\nInvalid output-ports')
            return
        
        else:
            self.router_id = self.config.get("router-id", "id")

            for key,value in self.config.items("input-ports"):
                self.ingress.append(value)

            for key,value in self.config.items("output-ports"):
                line_in_output = value.split('-')
                if line_in_output[1] == "1":
                    self.output_lines.append(value + "-Conn.")
                else:
                    self.output_lines.append(value + "-RIP")
                self.egress.append(line_in_output[2])
            
            # print(self.router_id)
            # print(self.ingress)
            # print(self.egress)
            # print(self.output_lines)
            # 1
            # ['1102', '1106', '1107']
            # ['2001', '6001', '8001']
            # ['2-1-2001-Conn.', '6-1-6001-Conn.', '8-1-8001-Conn.']
            
    
    def open_ports(self):
        for port in self.ingress:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", int(port)))
            self.ingress_sockets.append(sock)
    
    def recieve_message(self):
        message, _, _ = select.select(self.ingress_sockets, [], [], 15)
        current_time = time.time()
        
    
    def show_routes(self):
        print('Router ID: ', self.router_id)
        self.config.items("input-ports")
        for line in self.output_lines:
            line_in_output = line.split('-')
            
            ID = line_in_output[0]
            metric = line_in_output[1]
            out_port = line_in_output[2]
            route_type = line_in_output[3]
            if route_type == "Conn.":
                print(route_type + ' Router ' + ID + ', is directly connected, Port ' + out_port + ', Metric ' + metric)
            elif route_type == "RIP":
                print(route_type + ', Router ' + ID + ', is directly connected, Port ' + out_port + ', Metric ' + metric)


    def create_message(self):
        return

    def send_message(self):
        return

    def update_table(self):
        return

    
def main():
    print('RIP Router Demon')
    print('RIP Version: 2')
    config_file = sys.argv[1]
    demon = RIP_demon(config_file)

    demon.load_startup()
    demon.open_ports()
    demon.show_routes()
    
    #always,
    '''
    demon.recieve_message()
    '''

    #every 30 seconds,
    '''
    demon.create_message()
    demon.send_message()
    demon.update_table()
    '''

    # threading.Timer(10, demon.send_message).start()
    

    
main()
