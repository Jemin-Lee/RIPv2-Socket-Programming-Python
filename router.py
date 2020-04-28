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
        self.drop = []
        self.learned_routers = []
    

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
        now = datetime.now().time()
        print("=================Show Routes=================")
        print(now)
        print('Router ID: {}'.format(self.router_id))
        for key, value in self.config.items("output-ports"):
            line_in_output = value.split('-')

            ID = line_in_output[0]
            metric = line_in_output[1]
            out_port = line_in_output[2]
            next_hop = line_in_output[3]


            if metric == "16" and out_port == "N/A" and next_hop == "N/A":
                print('route to router {} invalidated'.format(ID))
            else:
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
        '''
        
        now = datetime.now().time()

        #create message
        update_message = pickle.dumps(self.message)

        print("==========Send Message===========")
        for port in self.neighbor_port:
            #sending router's whole output contents in pickle
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(update_message, ("127.0.0.1", int(port)))
            
            print("Update message sent to port " + port + ", " + str(now))


    def recieve_message(self):
        '''
        update routing config
        update output config
        implement Split Horizon (kinda, filters route to itself, could be better if the message itself doesn't contain that bit, yeah)
        '''
        print("==========Ports Open===========")
        print("listening for messages...")
        def update_table(route, sender):
            #write on our config file with key = reachable id and value = altered route line
            print("===============Update Routes=============")
            print('updating route, message from {}'.format(sender))
            current_table = dict(self.config.items("output-ports"))

            sender_id = list(sender.keys())[0]

            route_data = route.split("-")
            r_id = route_data[0]
            cost = route_data[1]
            port = route_data[2]
            next_hop = route_data[3]

            router_num = 'router{}'.format(r_id)
            sender_id_num = 'router{}'.format(sender_id)

            to_sender_route = current_table['router{}'.format(sender_id)].split('-')
            to_sender_cost = to_sender_route[1]
            potential_new_cost = int(to_sender_cost) + int(cost)


            def flush_(router):
                now = datetime.now().time()
                self.config.remove_option("output-ports", router)
                with open(self.file, 'w') as configfile:
                    self.config.write(configfile)
                print("===========Flush Route===========")
                print(now)
                print('route to {} flushed'.format(router))
                return
            flush_timer = Timer(60, flush_,[router_num])
            sender_flush_timer = Timer(60, flush_,[sender_id_num])

            def invalidate_(router):
                now = datetime.now().time()
                invalidated_route = '{}-{}-{}-{}'.format(router[-1], 16, 'N/A', 'N/A')
                print("===========Invalidation============")
                print(now)
                print('route invalidated: {}'.format(invalidated_route))

                self.config.set("output-ports", router, invalidated_route)
                with open(self.file, 'w') as configfile:
                    self.config.write(configfile)

                flush_timer.start()
                return
            invalid_timer = Timer(180, invalidate_,[router_num])
            sender_invalid_timer = Timer(180, invalidate_,[sender_id_num])


            sender_invalid_timer.cancel()
            sender_flush_timer.cancel()
            sender_invalid_timer.start()
            print('Invalid timer started for {}'.format(sender_id_num))

            if router_num in current_table:
                current_route = current_table[router_num]
                current_route_data = current_route.split('-')
                
                current_cost = current_route_data[1]
                current_port = current_route_data[2]
                current_next_hop = current_route_data[3]

                if current_next_hop == "N/A":
                    print("here")
                    print(route)
                    pass
                else:
                    if int(current_cost) <= potential_new_cost:
                        invalid_timer.cancel()
                        flush_timer.cancel()
                        invalid_timer.start()
                        print("No new routes")
                        return
                    else:
                        new_cost = potential_new_cost
                        new_route = '{}-{}-{}-{}'.format(r_id, new_cost, port, sender_id)
                        print('new route : {}'.format(new_route))
                        self.config.set("output-ports", router_num, new_route)
                        invalid_timer.cancel()
                        flush_timer.cancel()
                        invalid_timer.start()
                        return
            else:
                new_cost = potential_new_cost
                new_route = '{}-{}-{}-{}'.format(r_id, new_cost, port, sender_id)
                print('new route : {}'.format(new_route))
                self.config.set("output-ports", router_num, new_route)
                invalid_timer.start()
                print('Invalid timer started for {}'.format(router_num))
                return
            
        def triggered_update():
            '''
            triggered update
            '''
            return

        message, _, _ = select.select(self.ingress_sockets, [], [], 30)
        current_time = time.time()
        for s in message:
            print("===============Ports Closed===============")
            data, addr = s.recvfrom(1024)
            message_data = (pickle.loads(data))

            sender = message_data[0]
            update = message_data[1]
            
            for r_id in update:
                router = 'router{}'.format(self.router_id)
                if router == r_id:
                    #drop the route destined to myself
                    pass
                else:
                    update_table(update[r_id], sender)
        return


def main():
    
    print('RIP Router Demon')
    print('RIP Version: 2')
    config_file = sys.argv[1]
    demon = RIP_demon(config_file)
        
    def update_timer():
        demon.create_message()
        demon.send_message()
        demon.recieve_message()
        demon.show_routes()
        Timer(30, update_timer).start()

    demon.load_startup()
    demon.open_ports()
    demon.show_routes()
    update_timer()

main()