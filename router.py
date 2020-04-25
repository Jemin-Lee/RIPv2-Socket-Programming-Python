import configparser
import pickle
import sys
import select
import time
from threading import Timer
import socket
from datetime import datetime



class RIP_demon(object):
    def __init__(self, file):
        self.file = file
        self.router_id = None
        self.ingress = []
        self.ingress_sockets = []
        self.neighbor_port = []
        self.neighbor_id = []
        self.routes = {}
        self.message = []
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
            self.router_id = int(self.config.get("router-id", "id"))

            for key,value in self.config.items("input-ports"):
                self.ingress.append(value)
            
            for key,value in self.config.items("output-ports"):
                line_in_output = value.split('-')
                self.neighbor_id.append(line_in_output[0])
                self.neighbor_port.append(line_in_output[2])
            

    def open_ports(self):
        for port in self.ingress:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", int(port)))
            self.ingress_sockets.append(sock)
    

    def show_routes(self):
        print('Router ID: ', self.router_id)
        for key, value in self.config.items("output-ports"):
            line_in_output = value.split('-')

            ID = key
            metric = line_in_output[1]
            out_port = line_in_output[2]
            next_hop = line_in_output[3]

            if next_hop == "N/A":
                print(ID + ' directly connected, ' + out_port)
            else:
                print(ID + ' reachable via Port ' + out_port + ', Next Hop: ' + next_hop + ' Metric ' + metric)


    def create_message(self):
        '''
        update self.output_lines
        update with the config files, or
        update with the seperate source
        '''
        
        sender = {}
        sender.update({self.router_id:"update message"})
        for key,value in self.config.items("output-ports"):
            self.routes.update({key:value})
        
        self.message.append(sender)
        self.message.append(self.routes)


    def send_message(self):
        '''
        send to neighbors
        implement Split Horizon
        '''
        now = datetime.now().time()

        #create message
        update_message = pickle.dumps(self.message)

        for port in self.neighbor_port:
            #sending router's whole output contents in pickle
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(update_message, ("127.0.0.1", int(port)))
            print("Update message sent to port " + port + ", " + str(now))


    def recieve_message(self):
        '''
        update routing config
        update output config
        '''
        def update_table(route, sender):
            #write on our config file with key = reachable id and value = altered route line
            current_table = dict(self.config.items("output-ports"))

            sender_id = int(list(sender.keys())[0])

            route_data = route.split("-")
            r_id = int(route_data[0])
            cost = int(route_data[1])
            port = int(route_data[2])
            next_hop = route_data[3]

            print("message's router id = "+ r_id)
            print("my router's id = "+ self.router_id)
            print("two are equal {}".format(r_id == int(self.router_id)))
            if r_id == self.router_id:
                return
            else:
                if r_id in current_table:
                    current_route_data = current_table[r_id].split('-')
                    current_cost = current_route_data[1]
                    current_port = current_route_data[2]

                    if current_table[r_id] <= cost:
                        return
                    else:
                        new_cost = current_cost + cost
                        new_route = '{}-{}-{}-{}'.format(r_id, new_cost, current_port, sender_id)
                        self.config.set("output-ports", r_id, new_route)
                        return
                else:
                    new_route = '{}-{}-{}-{}'.format(r_id, cost, port, sender_id)
                    print(new_route)
                    self.config.set("output-ports", r_id, new_route)
                    return



        message, _, _ = select.select(self.ingress_sockets, [], [], 30)
        current_time = time.time()
        for s in message:
            data, addr = s.recvfrom(1024)
            message_data = (pickle.loads(data))

            sender = message_data[0]
            update = message_data[1]
            
            for r_id in update:
                if r_id == self.router_id:
                    #drop the route destined to myself
                    continue
                else:
                    update_table(update[r_id], sender)
        return








    # def invalid_table(self):
    #     '''
    #     poison reverse invalid routes
    #     '''


    # def flush_table(self):
    #     '''
    #     remove invalid routes
    #     '''
    #     return


    # def triggered_update(self):
    #     return
    


    
def main():
    

    # def invalid_timer():
    #     demon.invalid_table()
    #     Timer(180, invalid_timer).start()
        
    # def flush_timer():
    #     demon.flush_table()
    #     Timer(60, flush_timer).start()
    

    
    print('RIP Router Demon')
    print('RIP Version: 2')
    config_file = sys.argv[1]
    demon = RIP_demon(config_file)

    def update_timer():
        demon.create_message()
        demon.send_message()
        demon.recieve_message()
        Timer(30, update_timer).start()

    # def listen():
    #     while True:
    #         demon.recieve_message()

    demon.load_startup()
    demon.open_ports()
    demon.show_routes()
    update_timer()
main()
