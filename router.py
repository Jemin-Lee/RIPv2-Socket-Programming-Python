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
        self.timer.cancel()

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

        self.message = []


        self.triggered_message = []
        self.config = configparser.ConfigParser()
        self.drop = []
        self.learned_routers = []

        self.route_message = None
        self.sender_id = None
        self.current_table = None

        self.invalid_timer = {}
        self.flush_timer = {}


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
                self.neighbor_id.append(line_in_output[0])
                self.neighbor_port.append(line_in_output[2])
                sender_router = 'router{}'.format(line_in_output[0])
    

    def show_routes(self):
        '''
        reads all existing routes in the output ports and format them in a way that is readable and print
        '''
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
                print('route to router {} possibly down'.format(ID))
            else:
                if next_hop == "N/A":
                    print(ID + ' directly connected, ' + out_port)
                else:
                    print(ID + ' reachable via Port ' + out_port + ', Next Hop: ' + next_hop + ' Metric ' + metric)


    def create_message(self, dest_port):
        '''
        create message
        exclude routes that have the same destination port as the destination you are sending to
        '''
        source = {}
        routes = {}
        source.update({self.router_id:"update"})
        for key,value in self.config.items("output-ports"):
            if dest_port in value:
                pass
            else:
                routes.update({key:value})
        message = []
        message.append(source)
        message.append(routes)
        return message


    def send_message(self):
        '''
        sending messages to neighbor ports
        '''
        now = datetime.now().time()

        print("==========Send Message===========")
        for port in self.neighbor_port:
            #create message
            message = self.create_message(port)
            update_message = pickle.dumps(message)

            #sending router's whole output contents in pickle
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(update_message, ("127.0.0.1", int(port)))
            print(sock.getsockname())
            print("Update message sent to port " + port + ", " + str(now))


    def bind_socket(self):
        for port in self.ingress:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", int(port)))
            self.ingress_sockets.append(sock)
    

    def recieve_message(self):
        print("==========Ports Open===========")
        print("listening for messages...")

        #wait for 30 seconds for messages
        message, _, _ = select.select(self.ingress_sockets, [], [], 30)

        #current set to now
        current_time = time.time()

        #iterate through the current message
        for s in message:
            print("===============Ports Closed===============")
            data, addr = s.recvfrom(1024)
            #load the message
            message_data = (pickle.loads(data))

            #set the current sender_id
            '''
            example:
            self.message = [{2:"update message"}, {router1:route1, router2:route2}]
            '''
            self.sender_id = list(message_data[0].keys())[0]
            update = message_data[1]
            print(update)

            for r_id in update:
                self.route_message = update[r_id]
                self.update_table()

    
    def flush_(self, router):
        '''
        flush a route
        '''
        now = datetime.now().time()
        print("===========Flush Route===========")
        self.config.remove_option("output-ports", router)
        print(now)
        print('route to {} deleted'.format(router))
    

    def invalidate_(self, router):
        '''
        invalidate a route
        calls flush_timer
        '''
        now = datetime.now().time()
        invalidated_route = '{}-{}-{}-{}'.format(router[-1], 16, 'N/A', 'N/A')
        print("===========Invalidation============")
        self.config.set("output-ports", router, invalidated_route)
        print(now)
        print('route invalidated: {}'.format(invalidated_route))
        #call flush timer
        self.flush_timer[router] = routeTimer(60, self.flush_, router)
        self.flush_timer[router].start()


    def add_new_route(self, r_id, new_cost, port, sender_id):

        new_route = '{}-{}-{}-{}'.format(r_id, new_cost, port, sender_id)
        print('new route : {}'.format(new_route))
        dest_router = 'router{}'.format(r_id)
        self.config.set("output-ports", dest_router, new_route)


    def update_route(self, r_id, new_cost, port, sender_id):
        if port is None:
            #nothing happens to the current table
            print("No new routes")
        else:
            #update the current route
            new_route = '{}-{}-{}-{}'.format(r_id, new_cost, port, sender_id)
            print('new route : {}'.format(new_route))
            dest_router = 'router{}'.format(r_id)
            self.config.set("output-ports", dest_router, new_route)
    

    # def triggered_update(self, router, flush_timer):
    #     update_message = '{}-{}-{}-{}'.format(router, 16, 'N/A', 'N/A')
    #     update_message = pickle.dumps(update_message)
    #     print("==========Triggered Update===========")
    #     for port in self.neighbor_port:
    #         #sending router's whole output contents in pickle
    #         sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #         sock.sendto(update_message, ("127.0.0.1", int(port)))


    def update_table(self):
        '''
        takes a class variable self.message_route = e.g "2-3-3002-4"
        '''
        current_table = dict(self.config.items("output-ports"))
        
        route_message_data = self.route_message.split("-")
        to_sender_route_data = current_table['router{}'.format(self.sender_id)].split('-')

        sender_router = 'router{}'.format(self.sender_id)
        route_message_router = 'router{}'.format(route_message_data[0])

        potential_new_cost = int(route_message_data[1]) + int(to_sender_route_data[1])

        #write on our config file with key = reachable id and value = altered route line
        print("===============Update Routes=============")
        print('updating route, message from {}'.format(sender_router))

        router_id = route_message_data[0]
        new_cost = potential_new_cost
        next_hop = self.sender_id

        #check if the entry exists in the current table, if so, 
        if route_message_router in current_table.keys():

            current_route = current_table[route_message_router]
            current_route_data = current_route.split('-')

            if current_route_data[3] == "N/A":
                print("the router is directly connected")
                pass
            else:
                #it compares the cost, if current entry is better,
                if int(current_route_data[1]) <= potential_new_cost:
                    #destination port is set to none
                    dest_port = None
                else:
                    #if the new cost is better, the destination port is set to the new one
                    dest_port = current_route_data[2]
                self.update_route(router_id, new_cost, dest_port, next_hop)

                '''
                to test this,
                start only two routers,
                let one router learn a new route,
                turn off the other router,
                and then see if the router invalidate, and flush the aged route.
                '''
                #check if the entry router is in flush_timer
                if route_message_router in self.flush_timer.keys():
                    #if so, cancel the timer
                    self.flush_timer[route_message_router].cancel()
                #if not, reset the invalid timer anyway
                self.invalid_timer[route_message_router].cancel()
                self.invalid_timer[route_message_router].start()
                
        else:
            #if the new entry came in,
            dest_port = route_message_data[2]
            #calls add_new_route
            self.add_new_route(router_id, new_cost, dest_port, next_hop)

            #creates a new instance of timer for running the invalidate function
            #put into a dictionary with the entry router name as the key
            self.invalid_timer[route_message_router] = routeTimer(180, self.invalidate_, route_message_router)
            #starts the invalid timer for the specific route
            self.invalid_timer[route_message_router].start()
            print('Invalid timer started for {}'.format(route_message_router))


    


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
        Timer(30, update_timer).start()

    demon.load_startup()
    demon.bind_socket()
    demon.show_routes()
    
    update_timer()

main()
