import time
from queue import *
from logging import *
from threading import Thread

class SR_sender:
    def __init__(self, input_file, window_size, packet_len, nth_packet, send_queue, ack_queue, timeout_interval, logger):
        self.input_file = input_file
        self.window_size = window_size
        self.packet_len = packet_len
        self.nth_packet = nth_packet
        self.send_queue = send_queue
        self.ack_queue = ack_queue
        self.timeout_interval = timeout_interval
        self.logger = logger
        self.base = 0
        self.packets = self.prepare_packets()
        self.acks_list = [False] * len(self.packets)
        self.packet_timers = [0] * len(self.packets)
        self.dropped_list = []
        self.num_sent = 0
        self.thread = True
        self.expected_ack = 0
        self.buffer_queue = []
        self.logger.info(f"{len(self.packets)} packets created, Window size: {self.window_size}, Packet length: {self.packet_len}, Nth packed to be dropped: {self.nth_packet}, Timeout interval: {self.timeout_interval}")
    

    def prepare_packets(self):
        file = open(f"{self.input_file}", "r")
        words = file.read()
        binary_rep = "".join(format(ord(x),'08b') for x in words)
        data_bits = self.packet_len - 16
        packets = []
        seq_num = 0

        for i in range(0, len(binary_rep), data_bits):
            data = binary_rep[i:i + data_bits]
            if len(data) < data_bits:
                data = data + ('0' * (data_bits - len(data)))
            seq_padded = format(seq_num, '016b')
            packet = data + seq_padded
            packets.append(packet)
            seq_num += 1
        
        return packets
    

    def send_packets(self):
        for packet_num in range(self.base, min(self.base + self.window_size, len(self.packets))):
            seq_num = int(self.packets[packet_num][-16:], 2)
            if (self.acks_list[seq_num] == False):
                self.num_sent += 1
                self.logger.info(f"Sender: sending packet {seq_num}")
                if self.num_sent % self.nth_packet == 0:
                    self.dropped_list.append(seq_num)
                    self.logger.info(f"Sender: packet {seq_num} dropped")
                    self.packet_timers[packet_num] = time.time()
                else:
                    self.send_queue.put(self.packets[packet_num])
                    self.packet_timers[packet_num] = time.time()
            else:
                # Skip if acked. This shouldn't skip the first packet in the window after a timeout.
                continue
    

    def send_next_packet(self):
        self.base += 1
        packet_num = self.base + self.window_size - 1
        if (packet_num < len(self.packets)):
            self.num_sent += 1
            seq_num = int(self.packets[packet_num][-16:], 2)
            self.logger.info(f"Sender: sending packet {seq_num}")
            if self.num_sent % self.nth_packet == 0:
                self.dropped_list.append(seq_num)
                self.logger.info(f"Sender: packet {seq_num} dropped")
                self.packet_timers[packet_num] = time.time()
            else:
                self.send_queue.put(self.packets[packet_num])
                self.packet_timers[packet_num] = time.time()
    
    
    def check_timers(self):
        for packet_num in range(self.base, min(self.base + self.window_size, len(self.packets))):
            if self.packet_timers[packet_num] != 0:
                time_elapsed = time.time() - self.packet_timers[packet_num]
                if time_elapsed >= self.timeout_interval:
                    seq_num = int(self.packets[packet_num][-16:], 2)
                    self.logger.info(f"Sender: packet {seq_num} timed out")
                    self.packet_timers[packet_num] = 0
                    return True
    
        return False
    

    def receive_acks(self):
        while (self.thread):
            try:
                # This loop processess the buffered acks.
                while ((len(self.buffer_queue) > 0) and (self.buffer_queue[0] == self.expected_ack)):
                    buffered_ack = self.buffer_queue.pop(0)
                    self.expected_ack += 1
                    self.send_next_packet()
                
                ack = self.ack_queue.get(timeout=0.01)
                self.packet_timers[ack] = 0
                if (self.acks_list[ack] == False):
                    self.acks_list[ack] = True
                    if (ack == self.expected_ack):
                        self.logger.info(f"Sender: ack {ack} received")
                        self.expected_ack += 1
                        self.send_next_packet()
                    else:
                        self.buffer_queue.append(ack)
                        self.logger.info(f"Sender: ack {ack} received out of order, buffered")
                else:
                    self.logger.info(f"Sender: ack {ack} received")
            except Empty:
                continue
            except Exception as e:
                print(e)
    

    def stop_thread(self):
        self.thread = False


    def run(self):
        self.send_packets()
        Thread(target=self.receive_acks).start()
        while (self.base < len(self.packets)):
            if (self.check_timers() == True):
                self.send_packets()
        self.send_queue.put(None)
        self.logger.info("Sender: All packets have been sent and acknowledgments processed.")
        self.stop_thread()



class SR_receiver:
    def __init__(self, output_file, send_queue, ack_queue, logger):
        self.output_file = output_file
        self.send_queue = send_queue
        self.ack_queue = ack_queue
        self.logger = logger
        self.packet_list = []
        self.expected_seq_num = 0
        # Using a list instead of the queue library since I need to check the first element before dequeuing.
        self.buffer_queue = []
    

    def process_packet(self, packet):
        # This loop processess the buffered packets.
        while ((len(self.buffer_queue) > 0) and (int(self.buffer_queue[0][-16:], 2) == self.expected_seq_num)):
            buffered_packet = self.buffer_queue.pop(0)
            buff_seq_num = int(buffered_packet[-16:], 2)
            self.packet_list.append(buffered_packet)
            self.ack_queue.put(buff_seq_num)
            self.expected_seq_num += 1
            self.logger.info(f"Receiver: packet {buff_seq_num} received")

        seq_num = int(packet[-16:], 2)
        if (seq_num == self.expected_seq_num):
            self.packet_list.append(packet)
            self.ack_queue.put(seq_num)
            self.expected_seq_num += 1
            self.logger.info(f"Receiver: packet {seq_num} received")
            return True
        
        else:
            self.ack_queue.put(seq_num)
            self.buffer_queue.append(packet)
            self.logger.info(f"Receiver: packet {seq_num} received out of order, stored in buffer")
            return False
    

    def write_to_file(self):
        data = []
        for packet_num in range(0, len(self.packet_list)):
            packet = self.packet_list[packet_num][:-16]
            for i in range(0, len(packet), 8):
                byte = packet[i:i+8]
                if byte != "00000000":
                    char = chr(int(byte, 2))
                    data.append(char)
        message = "".join(data)

        try:
            output_file = open(self.output_file, "w")
            output_file.write(message)
            output_file.close()
        except Exception as e:
            print(e)
    

    def run(self):
        while True:
            try:
                packet = self.send_queue.get(timeout=0.01)
                if packet == None:
                    break
                else:
                    self.process_packet(packet)
            except Empty:
                continue
            except Exception as e:
                print(e)
        self.write_to_file()