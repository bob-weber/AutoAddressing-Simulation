import settings
import random
Terminate = False

def exec(SlaveID, IncomingMsg, OutgoingMsg):
	minAddress = settings.DefaultMinAddress
	maxAddress = settings.DefaultMaxAddress
	actualAddress = settings.InvalidAddress
	#print("Spawned slave ", SlaveID)

	while True:
		# Wait for a message
		message = IncomingMsg.get(block=True)

		# All messages have an address in first paramter, command in 2nd.
		# Beyond that, data is message dependent.
		if ((message[0] == 0) or
			((message[0] == actualAddress) and (actualAddress != settings.InvalidAddress))):
			# This message is broadcast, or intended for us after we've created a valid address
			if message[1] == 'SetAddressRange':
				# We get a min and max value
				minAddress = message[2]
				maxAddress = message[3]

			elif message[1] == 'RandomizeAddresses':
				AddressesToNotUse = message[2]
				#print("Rand: Slave=", SlaveID, ", Addr=", actualAddress, ", RsvdAddr=", AddressesToNotUse)
				RandomizeCount = 0
				actualAddress = random.randint(minAddress, maxAddress)
				#if len(AddressesToNotUse) > 0:
				#	print("Slave:", SlaveID, "AddrToAVoid:", AddressesToNotUse)
				#	print("Slave:", SlaveID, "RandCnt:", RandomizeCount, "Addr:",actualAddress)
				while actualAddress in AddressesToNotUse:
					actualAddress = random.randint(minAddress, maxAddress)
					RandomizeCount += 1
				#print("Slave ", SlaveID, ", RandCnt:", RandomizeCount)
				if (RandomizeCount > 100):
						# Well, something is wrong
						print("Slave ", SlaveID, " stuck randomizing address")

			elif message[1] == 'RetrieveUniqueID':
				# We don't respond to a broadcast here. Verify this not a broadcast message.
				if (message[0] == actualAddress):
					UniqueIDMsg = [actualAddress, message[1], SlaveID]
					# print("Slave ", SlaveID, " UniqueID: ", UniqueIDMsg)
					OutgoingMsg.put(UniqueIDMsg)

			elif message[1] == 'Quit':
				# Tell the slave msg processor we're closing. This is a kokey way to close a thread, but ...
				TerminatingMsg = [actualAddress, 'Quit']
				OutgoingMsg.put(TerminatingMsg)
				# Close this thread
				break

			else:
				print("Invalid slave command: slave=", SlaveID, "cmd=", message[0])

		# else, message not for us
	# while loop
