import configparser
import pickle
import sys
import select
import time
import threading

def load_startup(file):
    return

class RIP_demon(object):
    def __init__(self, router_id, ingress, egress):
        self.router_id = router_id
        self.ingress = ingress
        self.egress = egress
        self.neighbors = []
    
    def open_ports(self):
        return
    
    def create_message(self):
        return

    def send_message(self):
        return

    def routing_update(self):
        return

    def update_table(self):
        return

    def show_route(self):
        return

    


def main():
    config_file = sys.argv[1]
    router_id, ingress, egress = load_startup(config_file)
    demon = RIP_demon(router_id, ingress, egress)
    threading.Timer(30, demon.send_message).start()

    
main()
