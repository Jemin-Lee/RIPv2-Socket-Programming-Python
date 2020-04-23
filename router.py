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
        self.neighbor_port = []
        self.neighbor_id = []
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
                self.output_lines.append(value)
                line_in_output = value.split('-')
                self.neighbor_id.append(line_in_output[0])
                self.neighbor_port.append(line_in_output[2])
                
            

    def open_ports(self):
        for port in self.ingress:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", int(port)))
            self.ingress_sockets.append(sock)
    

    def recieve_message(self):
        message, _, _ = select.select(self.ingress_sockets, [], [], 180)
        current_time = time.time()
    

    def show_routes(self):
        print('Router ID: ', self.router_id)
        for line in self.output_lines:
            line_in_output = line.split('-')

            ID = line_in_output[0]
            metric = line_in_output[1]
            out_port = line_in_output[2]
            next_hop = line_in_output[3]

            if next_hop == "N/A":
                print(ID + ' directly connected, ' + out_port)
            else:
                print(ID + ' reachable via Port ' + out_port + ', Next Hop: ' + next_hop + ' Metric ' + metric)


    def create_message(self):
        '''
        make copy of the current routing config
        '''


    def send_message(self):
        '''
        send to neighbors
        implement Split Horizon
        '''
        return

    def update_table(self):
        '''
        update routing config
        '''
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
    '''

    #every 180 seconds
    '''
    demon.update_table()
    '''
    # threading.Timer(10, demon.send_message).start()
    

    
main()
