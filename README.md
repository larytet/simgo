The task requires implementation of several small components which simulates a very simple network protocol stack.



2 Upper layers:

------------

1. A byte generator which generates a random number of bytes in the range of 0 <= n <= 7 every 400ms and send them out to a transport layer.

2. A byte printer which gets bytes from a transport layer and prints them to the screen.



A transport layer:

------------------

A layer which can accept bytes from an upper layer or a "Physical" layer.

- When bytes are accepted from an upper layer they are sent to a "Physical" layer.

- When bytes are received from a "physical" layer they are sent to an upper layer.



2 Physical layers:

------------------

- A physical layer gets bytes from a transport layer or another physical layer.

- When bytes are accepted from transport layer they are sent to another physical layer.

- When bytes are received from a physical layer they are sent to a transport layer.

- There should be two physical layers:

1. A byte physical layer, which simply sends each byte it receives.

2. A packet physical layer, which accumulates the bytes and sends them out as a packet.

   A packet is sent if 10 bytes are accumulated or if less than 10 bytes have been accumulated but 1 second has passed since the first byte was received.



All components shall have init functions which sets which other components they are linked to.



4 Executable:

-------------

After all of the above is ready, it should be easy to create and test the following executable:

1. byte generator -> transport -> byte physical -> byte physical -> transport -> byte printer

2. byte generator -> transport -> packet physical -> packet physical -> transport -> byte printer

3. byte generator -> transport -> byte physical -> packet physical -> transport -> byte printer

4. byte generator -> transport -> packet physical -> byte physical -> transport -> byte printer

5. Example of execution:

-------------

Configure Byte Generator -> Transport -> PacketPHY -> BytePHY -> Transport -> Byte Printer
./task1.py pipeline --stages GTPBTR
  
Configure Byte Generator -> Transport -> BytePHY -> BytePHY -> Transport -> Byte Printer
./task1.py pipeline --stages GTBBTR
  

