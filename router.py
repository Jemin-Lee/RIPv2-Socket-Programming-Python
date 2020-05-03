import configparser
import pickle
import sys
import select
import time
from threading import Timer
import socket
from datetime import datetime

class routeTimer(object):
    '''
    this class is used to implement
    - invalid timer
    - flush timer
    '''
    def __init__(self, interval, f, *args, **kwargs):
        '''
        parameter:
        - interval, time it should wait before running the function
        - function
        - args, parameter that the function processes
        '''
        self.interval = interval
        self.f = f
        self.args = args
        self.kwargs = kwargs
        self.timer = None

    def call(self):
        self.f(*self.args, **self.kwargs)

    def cancel(self):
        '''
        stop the timer
        '''
        if self.timer is not None:
            self.timer.cancel()
        else:
            pass

    def start(self):
        '''
        start the timer
        '''
        self.timer = Timer(self.interval, self.call)
        self.timer.start()

class RIP_demon(object):
    '''
    router class
    '''
    def __init__(self, file):
        self.file = file
        self.router_id = None
        self.ingress = []
        self.ingress_sockets = []
        self.neighbor_port = []
        self.neighbor_id = []
        self.routes = {}
        self.config = configparser.ConfigParser()
        self.learned_routers = []
        self.route_message = None
        self.sender_id = None
        self.current_table = None
        self.invalid_timer = {}
        self.flush_timer = {}
        self.neighbors = {}

    def load_startup(self):
        '''
        reads the initial config file
        '''
        self.config.read(self.file)
        
        #does checks for the config file
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

            #collects input ports into list
            for key,value in self.config.items("input-ports"):
                self.ingress.append(value)
            
            #collect neighbor id and destination port in seperate lists
            for key,value in self.config.items("output-ports"):
                line_in_output = value.split('-')
                self.routes[key] = line_in_output
                self.neighbor_id.append(line_in_output[0])
                self.neighbor_port.append(line_in_output[2])
            
            for key,value in self.config.items("output-ports"):
                line_in_output = value.split('-')
                self.neighbors[key] = line_in_output
                self.invalid_timer[key] = routeTimer(45, self.invalidate_, key)
                self.flush_timer[key] = routeTimer(60, self.flush_, key)
                self.invalid_timer[key].start()

    def show_routes(self):
        '''
        reads all existing routes in the output ports and format them in a way that is readable and print
        '''
        now = datetime.now().time()
        print("!")
        print("!")
        print("!")
        print("Show Routes")
        print('Router ID: {}, {}'.format(self.router_id, now))
        for key in self.routes:
            output = self.routes[key]
            ID = output[0]
            metric = output[1]
            out_port = output[2]
            next_hop = output[3]

            if metric == "16":
                print('route to router {} possibly down'.format(ID))
            else:
                if next_hop == "N/A":
                    print('router {} directly connected, {}'.format(ID, out_port))
                else:
                    print('rotuer {} reachable via Port {}, Next Hop: {} Metric: {}'.format(ID, out_port, next_hop, metric))

    def create_message(self, dest_port):
        '''
        create message
        exclude routes that have the same destination port as the destination you are sending to
        '''
        source = {}
        routes = {}
        source.update({self.router_id:"update"})
        for key in self.routes:
            '''
            exclude if those routes were learnt, or configured via a port, 
            that the message is destined to the same port.
            (implementing split horizon)
            '''
            if dest_port in self.routes[key] or int(self.routes[key][1]) >= 16:
                pass
            else:
                routes[key]=self.routes[key]
        message = []
        message.append(source)
        message.append(routes)
        return message

    def send_message(self):
        '''
        sending messages to neighbor ports
        '''
        now = datetime.now().time()
        print("!")
        print("!")
        for port in self.neighbor_port:
            #create message 
            message = self.create_message(port)
            update_message = pickle.dumps(message)
            #sending router's whole output contents in pickle
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(update_message, ("127.0.0.1", int(port)))
            print('{}, Update message sent to port {}'.format(now, port))
    
    def rip_trigger(self,router, route):
        '''
        send triggered update
        avoid the parameter port from sending messages
        '''
        source = {}
        source.update({self.router_id:"trigger"})
        Tmessage = pickle.dumps([source, route])

        print("!")
        print("!")
        for port in self.neighbor_port:
            if route[2] == port:
                pass
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(Tmessage, ("127.0.0.1", int(port)))
                print('RIP trigger message sent to port {}'.format(port))
    

    def bind_socket(self):
        for port in self.ingress:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", int(port)))
            self.ingress_sockets.append(sock)
    
    def recieve_message(self):
        now = datetime.now().time()
        #wait for 30 seconds for messages
        message, _, _ = select.select(self.ingress_sockets, [], [], 12)
        #current set to now
        current_time = time.time()
        #iterate through the current message
        for s in message:
            data, addr = s.recvfrom(1024)
            #load the message
            message_data = (pickle.loads(data))
            #set the current sender_id
            self.sender_id = list(message_data[0].keys())[0]
            sender_router = 'router{}'.format(self.sender_id)
            update = message_data[1]

            if list(message_data[0].values())[0] == "update":
                if sender_router in self.invalid_timer.keys():
                    self.routes.pop(sender_router)
                    self.routes[sender_router] = self.neighbors[sender_router]
                    if sender_router in self.flush_timer.keys():
                        self.flush_timer[sender_router].cancel()
                    self.invalid_timer[sender_router].cancel()
                    self.invalid_timer[sender_router].start()
                else:
                    self.invalid_timer[sender_router] = routeTimer(45, self.invalidate_, sender_router)
                    self.flush_timer[sender_router] = routeTimer(60, self.flush_, sender_router)
                    self.invalid_timer[sender_router].start()
                    if sender_router in self.neighbors.keys():
                        self.routes[sender_router] = self.neighbors[sender_router]
                print("!")
                print('{}, message from router {}'.format(now, self.sender_id))
                print("!")
                for r_id in update:
                    self.route_message = update[r_id]
                    self.update_table()

            else:
                if 'router{}'.format(message_data[1][0]) in self.routes.keys():
                    print("!")
                    print('recieved trigger update from {}'.format(self.sender_id))
                    self.invalid_timer['router{}'.format(message_data[1][0])] = routeTimer(45, self.invalidate_, 'router{}'.format(message_data[1][0]))
                    self.flush_timer['router{}'.format(message_data[1][0])] = routeTimer(60, self.flush_, 'router{}'.format(message_data[1][0]))
                    self.invalidate_('router{}'.format(message_data[1][0]), True)
                else:
                    print("!")
                    print('RIP Triggered, no update from {}'.format(sender_router))
                    pass

    
    def flush_(self, router):
        '''
        flush a route
        '''
        now = datetime.now().time()
        if router in self.routes.keys():
            self.routes.pop(router)
            self.flush_timer.pop(router)
            self.invalid_timer.pop(router)
        print('{} route to {} deleted'.format(now, router))
    
    def invalidate_(self, router, trigger=False):
        '''
        invalidate a route
        calls flush_timer
        '''
        now = datetime.now().time()
        self.routes[router][1] = "16"
        self.rip_trigger(router, self.routes[router])
        if trigger:
            self.invalid_timer[router].cancel()
            print("!")
            print('{}, {} down according to trigger update from router {}'.format(now, router, self.sender_id))
        else:
            print("!")
            print('{}, {} invalid'.format(now, router))
        self.flush_timer[router].start()
        #call flush timer
        

    def update_route(self, id, cost, port, sender_id):
        dest_router = 'router{}'.format(id)
        self.routes[dest_router] = [id, cost, port, sender_id]
        print("!")
        print('{} reachable via Port {} , Next Hop: {}, Metric: {}'.format(id, port, sender_id, cost))

    def update_table(self):
        '''
        takes a class variable self.message_route = e.g "2-3-3002-4"
        self.route_message = [1,2,3001,5]
        '''
        sender_router = 'router{}'.format(self.sender_id)
        dest_router = 'router{}'.format(self.route_message[0])

        potential_new_cost = int(self.route_message[1]) + int(self.routes[sender_router][1]) + 1 #hop count 1

        #write on our config file with key = reachable id and value = altered route line
        print("!")
        print('updating route, message from {}'.format(sender_router))

        if potential_new_cost > 15:
            print("!")
            print('Metric 15 exceeded, router {} unreachable'.format(self.route_message[0]))
            pass
        else:
            #check if the entry exists in the current table, if so, 
            if dest_router in self.routes.keys():
                #it compares the cost, if current entry is better,
                if int(self.routes[dest_router][1]) <= potential_new_cost:
                    print("no new routes")
                    pass
                else:
                    #if the new cost is better, the destination port is set to the new one
                    self.update_route(self.route_message[0], potential_new_cost, self.routes[dest_router][2], self.sender_id)
                '''
                to test this,
                start only two routers,
                let one router learn a new route,
                turn off the other router,
                and then see if the router invalidate, and flush the aged route.
                '''
                #entry router is in flush_timer, so cancel the timer
                self.flush_timer[dest_router].cancel()
                self.invalid_timer[dest_router].cancel()
                self.invalid_timer[dest_router].start()
                    
            else:
                #if the new entry came in, add a new route
                self.update_route(self.route_message[0], potential_new_cost, self.routes[sender_router][2], self.sender_id)
                #creates a new instance of timer for running the invalidate and flush function
                #put into a dictionary with the entry router name as the key
                self.invalid_timer[dest_router] = routeTimer(45, self.invalidate_, dest_router)
                self.flush_timer[dest_router] = routeTimer(60, self.flush_, dest_router)
                #starts the invalid timer for the specific route
                self.invalid_timer[dest_router].start()
                print("!")
                print('Invalid timer started for {}'.format(dest_router))


def main():
    print('RIP Router Demon')
    print('RIP Version: 2')
    config_file = sys.argv[1]
    demon = RIP_demon(config_file)
        
    def update_timer():
        '''
        function called every 30 seconds, implementing periodic update
        '''
        demon.send_message()
        demon.recieve_message()
        demon.show_routes()
        #timer execute every 30 sec
        Timer(12, update_timer).start()

    demon.load_startup()
    demon.bind_socket()
    demon.show_routes()
    update_timer()

main()
