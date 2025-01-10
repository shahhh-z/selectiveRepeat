# SelectiveRepeat
My implementation of a Selective Repeat (SR) protocol. It is a modified version of my [Go-Back-N (GBN)](https://github.com/shahhh-z/Go-Back-N) protocol. The main difference between the two protocols is that any packets or acks that are received out of order are not dropped and are instead buffered. Once the packet/ack needed arrives, the buffered packets/acks can be popped from the queue.

This takes around 6 seconds to execute, the range I got was 4 seconds to 8 seconds.

# How to Run
Simply download all of the files and run the test file in an IDE. An example log of the test is included in this repository.
