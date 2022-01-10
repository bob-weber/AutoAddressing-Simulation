import threading
import queue
import time
import collections
# import sys
import Slave
import settings

SlaveThreads = []

# This is a dictionary that lists all the slaves that've requested each address
RequestedAddressesDict = collections.defaultdict(list)
AcceptedAddressDict = {}
TransactionCount = 0
TimeoutCount = 0


def ProcessSlaveMsgs(RxQueue):
	global Terminate
	while True:
		message = RxQueue.get(block=True)
		# We got a response
		global TransactionCount
		global TimeoutCount
		TimeoutCount -= 1			# Undo the increment of timeouts when we sent the message.
		TransactionCount += 1		# And increment our count of round-trip transactions.

		if message[1] == 'RetrieveUniqueID':
			# Save slave addresses to our list
			key = message[0]
			slaveID = message[2]
			RequestedAddressesDict[key].append(slaveID)

		elif message[1] == 'Quit':
			break

def SendSlaveMsg(message):
	# We always send the message to all slaves, just like in Modbus. They decide if they should respond.
	for SlaveID in range(settings.NumberOfSlaves):
		MastertoSlaveQueues[SlaveID].put(message)
	# For heuristics, increment global transaction and timeoiut count
	# If we get a response, we'll decreemnt the timeout count, since we didn't time out.
	global TimeoutCount
	TimeoutCount += 1

# This function will send a Randomize message to each slave.
# The addressed slaves will respond with a new address.
# Inputs:	UsedAddressesList - List of unavailable addresses.
#			AddressToRandomize - Address to randomize. Can be the broadcast address.
# Outputs:	ConfictAddressList - List of addresses that have multiple slaves.
# Note: We assume the slaves do not use any of the addresses we send as used. This is a proof of concept, not a
#		robust implementation.
def RandomizeSlaves(UsedAddressesList, ConfictAddressList, Broadcast):
	#print("Rand, Used:", UsedAddressesList, ", Conflict:", ConfictAddressList, ", BCast:", Broadcast)
	if Broadcast:
		RandomizeAddressMsg = [settings.BroadcastAddress, 'RandomizeAddresses', UsedAddressesList]
		SendSlaveMsg(RandomizeAddressMsg)
		#print("Send Slave1: ", RandomizeAddressMsg)
		time.sleep(settings.ModbusTransactionTime_sec)  # wait 50 ms

	else:
		# send only to conflict addresses
		for Address in ConfictAddressList:
			RandomizeAddressMsg = [Address, 'RandomizeAddresses', UsedAddressesList]
			SendSlaveMsg(RandomizeAddressMsg)
			#print("Send Slave2: ", RandomizeAddressMsg)
			time.sleep(settings.ModbusTransactionTime_sec)  # wait 50 ms

	# Now, send a message to retrieve the addresses from the AddressToRandomize
	RequestedAddressesDict.clear()
	ConfictAddressList.clear()			# clear conflicts. We'll see if we still have any.

	#if (AddressToRandomize == settings.BroadcastAddress):
	# All slaves have randomized. Try and read each of their iDs
	# Note: range goes up to max-1, so to read at the max address we need to add 1
	for ReadAddress in range(minAddress, maxAddress+1, 1):
		if ReadAddress not in UsedAddressesList:
			# Query for slaves at this address.
			RetrieveUniqueIDMsg = [ReadAddress, 'RetrieveUniqueID']
			SendSlaveMsg(RetrieveUniqueIDMsg)
			#print("Send Slave3: ", RetrieveUniqueIDMsg)
			time.sleep(settings.ModbusTransactionTime_sec)  # wait 50 ms
	# else, skip this address. A slave already has it reserved.
	#else:
	#	# send to just one address
	#	RetrieveUniqueIDMsg = [AddressToRandomize, 'RetrieveUniqueID', UsedAddressesList]
	#	SendSlaveMsg(RetrieveUniqueIDMsg)

	# All slaves should've reported. Let's see what we have
	#print("Req Addresses: ", RequestedAddressesDict)

	# Go through our requested addresses
	# Addresses with a single slave are copied to AcceptedAddressDict, and
	# the address added to UsedAddressesList.
	# Multiple slaves at an address are added to AcceptedAddressDict
	for key in RequestedAddressesDict:
		if len(RequestedAddressesDict[key]) == 1:
			# Move this address to the accepted list, and clear it
			AcceptedAddressDict[key] = RequestedAddressesDict[key][0]
			UsedAddressesList.append(key)
		else:
			ConfictAddressList.append(key)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
	# Create an outbound queue, from the master to the slaves, and
	# an inbound queue for slave responses.
	MastertoSlaveQueues = []
	SlavesToMasterQueue = queue.Queue()
	ConfictAddressList = []
	UsedAddressesList = []			# used addresses. Not available for new slaves.

	# Define a list for each slave. Also create an incoming and outgoing queue for each slave.
	for i in range(settings.NumberOfSlaves):
		MastertoSlaveQueues.append(queue.Queue())
		SlaveThreads.append(threading.Thread(target=Slave.exec, args=(i, MastertoSlaveQueues[i], SlavesToMasterQueue)))
		SlaveThreads[i].start()

	# Start slave response thread
	SlaveResponseThread = threading.Thread(target=ProcessSlaveMsgs, args=(SlavesToMasterQueue,))
	SlaveResponseThread.start()

	minAddress = settings.DefaultMinAddress
	maxAddress = settings.DefaultMaxAddress

	# User menu
	while True:
		print("""
		1) Set address range
		2) Start auto-addressing
		q) exit/quit.
		""")
		menuInput = input("Select menu item> ")
		try:
			if menuInput == '1':
				minAddress = int(input("minimum address> "))
				maxAddress = int(input("maximum address> "))
				if (minAddress <= settings.DefaultMaxAddress) and (maxAddress >= settings.DefaultMinAddress):
					# Send address range
					SetAddressRangeMsg = [settings.BroadcastAddress, 'SetAddressRange', minAddress, maxAddress]
					SendSlaveMsg(SetAddressRangeMsg)
				else:
					raise ValueError()

			elif menuInput == '2':
				UsedAddressesList.clear()
				ConfictAddressList.clear()
				AcceptedAddressDict.clear()
				RandomizeCount = 1
				TransactionCount = 0
				TimeoutCount = 0

				RandomizeSlaves(UsedAddressesList, ConfictAddressList,  True)
				while len(ConfictAddressList) > 0:
					RandomizeCount += 1
					if (RandomizeCount < 100):
						# We have conflicts. Take one conflict and try and resolve it.
						RandomizeSlaves(UsedAddressesList, ConfictAddressList, False)
					else:
						print("Failed after 100 tries")
						break

				# Done
				# Print the results
				print("Randomization took ", RandomizeCount, " cycles, ", TransactionCount, " Msg transactions; ", TimeoutCount, " Timeouts")
				print("Time: ", (settings.ModbusTransactionTime_sec * TransactionCount) + (settings.ModbusTimeoutTime_sec * TimeoutCount),
					  " secs, at ", settings.ModbusTransactionTime_sec, " secs/msg.")
				print("Final dictionary (Address:SlaveID): ", AcceptedAddressDict)

			elif menuInput == 'q':
				QuitMsg = [settings.BroadcastAddress, 'Quit']
				SendSlaveMsg(QuitMsg)
				break   # break out of loop and exit

		except ValueError:
			print("Invalid input. Use an int")

	for thread in SlaveThreads:
		thread.join()
	SlaveResponseThread.join()
	#exit()
